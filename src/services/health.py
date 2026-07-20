"""Rich /health payload (OSS §2.3 setup + §5.1 databases/data/warnings)."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import redis
from sqlalchemy import func, select, text

from src.graph.connection import is_available
from src.graph.queries import graph_age_hours
from src.models import Job, JobSourceConfig, Stats, get_sync_db
from src.models.database import sync_engine
from src.services.setup_status import get_setup_status

_STARTED_AT = time.monotonic()


def _probe_postgres() -> str:
    try:
        with sync_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "connected"
    except Exception:
        return "unavailable"


def _probe_redis() -> str:
    try:
        from src.config import settings

        client = redis.from_url(settings.redis_url, socket_connect_timeout=2)
        client.ping()
        client.close()
        return "connected"
    except Exception:
        return "unavailable"


def _probe_neo4j() -> str:
    return "connected" if is_available() else "unavailable"


def _next_poll_iso(now: datetime) -> str:
    next_even = (now.hour // 2 + 1) * 2
    if next_even < 24:
        nxt = now.replace(hour=next_even, minute=0, second=0, microsecond=0)
    else:
        nxt = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    return nxt.isoformat()


def build_health_payload() -> dict:
    setup = get_setup_status()
    databases = {
        "postgres": _probe_postgres(),
        "redis": _probe_redis(),
        "neo4j": _probe_neo4j(),
    }

    total_active = 0
    total_companies = 0
    sources_active = 0
    sources_with_errors = 0
    last_poll = None
    last_poll_age_minutes = None
    graph_last_built = None
    now = datetime.now(UTC)

    try:
        with get_sync_db() as db:
            stats = db.scalars(select(Stats)).first()
            if stats:
                total_active = stats.total_active_jobs or 0
                total_companies = stats.total_companies or 0
                if stats.last_full_poll_at:
                    last_poll = stats.last_full_poll_at.isoformat()
                    last_poll_age_minutes = (
                        now - stats.last_full_poll_at
                    ).total_seconds() / 60.0
            else:
                total_active = (
                    db.scalar(
                        select(func.count()).select_from(Job).where(Job.status == "active")
                    )
                    or 0
                )
                total_companies = (
                    db.scalar(
                        select(func.count(func.distinct(Job.company_name))).where(
                            Job.status == "active"
                        )
                    )
                    or 0
                )
            sources_active = (
                db.scalar(
                    select(func.count())
                    .select_from(JobSourceConfig)
                    .where(JobSourceConfig.active.is_(True))
                )
                or 0
            )
            sources_with_errors = (
                db.scalar(
                    select(func.count())
                    .select_from(JobSourceConfig)
                    .where(
                        JobSourceConfig.active.is_(True),
                        JobSourceConfig.last_error.is_not(None),
                    )
                )
                or 0
            )
    except Exception:
        pass

    graph_ok = databases["neo4j"] == "connected"
    age = graph_age_hours() if graph_ok else None
    if graph_ok and age is not None:
        built_at = now - timedelta(hours=age)
        graph_last_built = built_at.isoformat()

    warnings: list[str] = []
    if last_poll_age_minutes is not None and last_poll_age_minutes > 150:
        warnings.append(
            "Polling may be delayed. Last successful poll was over 2.5 hours ago."
        )
    if sources_with_errors > 50:
        warnings.append(f"{sources_with_errors} active sources report last_error.")
    for name, state in databases.items():
        if state != "connected":
            warnings.append(f"{name} is unavailable.")
    if graph_ok and age is not None and age > 6:
        warnings.append("Graph data older than 6 hours.")

    status = "ok"
    if any(v != "connected" for v in databases.values()):
        status = "degraded"
    elif last_poll_age_minutes is not None and last_poll_age_minutes > 300:
        status = "degraded"
    elif setup["sources_configured"] > 0 and not setup["first_poll_complete"]:
        status = "starting"

    return {
        "status": status,
        "version": "0.1.0",
        "uptime_seconds": round(time.monotonic() - _STARTED_AT, 1),
        "setup": setup,
        "databases": databases,
        "data": {
            "total_active_jobs": total_active,
            "total_companies": total_companies,
            "total_sources_active": sources_active,
            "sources_with_errors": sources_with_errors,
            "last_poll": last_poll,
            "last_poll_age_minutes": (
                round(last_poll_age_minutes, 1)
                if last_poll_age_minutes is not None
                else None
            ),
            "next_poll": _next_poll_iso(now),
            "graph_last_built": graph_last_built,
        },
        "warnings": warnings,
        # Keep legacy keys for existing clients during OSS transition.
        "graph": "ok" if graph_ok else "unavailable",
        "graph_age_hours": age,
    }
