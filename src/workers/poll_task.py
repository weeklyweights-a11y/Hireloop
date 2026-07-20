from __future__ import annotations

import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from urllib.parse import urlparse

import structlog
from sqlalchemy import select

from src.config import settings
from src.models import JobSourceConfig, get_sync_db
from src.services.poller import poll_source
from src.workers.celery_app import celery_app
from src.workers.stats_task import refresh_stats

logger = structlog.get_logger()

SLEEP_BETWEEN_SAME_DOMAIN = 0.5


def group_configs_by_domain(configs: list) -> dict[str, list]:
    groups: dict[str, list] = defaultdict(list)
    for config in configs:
        domain = urlparse(config.api_endpoint or "").netloc or "unknown"
        groups[domain].append(config)
    return dict(groups)


def _poll_one(config_id) -> dict:
    try:
        with get_sync_db() as db:
            config = db.get(JobSourceConfig, config_id)
            if config is None:
                return {
                    "ok": False,
                    "company": str(config_id),
                    "status": "missing",
                }
            result = poll_source(config, db)
        return {
            "ok": result.status == "success",
            "company": result.company_name,
            "status": result.status,
            "new": result.jobs_new,
            "updated": result.jobs_updated,
            "closed": result.jobs_closed,
        }
    except Exception as exc:
        logger.exception("poll_crashed", config_id=str(config_id))
        return {
            "ok": False,
            "company": str(config_id),
            "status": "crashed",
            "error": str(exc),
        }


def _poll_domain_sequential(config_ids: list) -> list[dict]:
    out = []
    for i, cid in enumerate(config_ids):
        out.append(_poll_one(cid))
        if i < len(config_ids) - 1:
            time.sleep(SLEEP_BETWEEN_SAME_DOMAIN)
    return out


@celery_app.task(name="src.workers.poll_task.poll_all_sources")
def poll_all_sources() -> dict:
    started = time.monotonic()
    with get_sync_db() as db:
        configs = list(
            db.scalars(select(JobSourceConfig).where(JobSourceConfig.active)).all()
        )
        # detach ids + endpoints before leaving session
        items = [(c.id, c.api_endpoint or "") for c in configs]

    by_domain: dict[str, list] = defaultdict(list)
    for cid, endpoint in items:
        domain = urlparse(endpoint).netloc or "unknown"
        by_domain[domain].append(cid)

    results: list[dict] = []
    workers = max(1, settings.max_poll_concurrency)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_poll_domain_sequential, ids): domain
            for domain, ids in by_domain.items()
        }
        for fut in as_completed(futures):
            results.extend(fut.result())

    succeeded = sum(1 for r in results if r.get("ok"))
    failed = len(results) - succeeded
    failed_sources = [r["company"] for r in results if not r.get("ok")]
    new = sum(int(r.get("new") or 0) for r in results)
    updated = sum(int(r.get("updated") or 0) for r in results)
    closed = sum(int(r.get("closed") or 0) for r in results)

    with get_sync_db() as db:
        stats = refresh_stats(db, last_full_poll_at=datetime.now(UTC))
        total_active = int(stats.total_active_jobs or 0)

    duration_s = time.monotonic() - started
    summary = {
        "event": "poll_cycle_complete",
        "sources_polled": len(results),
        "succeeded": succeeded,
        "failed": failed,
        "jobs_new": new,
        "jobs_updated": updated,
        "jobs_closed": closed,
        "total_active": total_active,
        "duration_seconds": round(duration_s, 1),
        "failed_sources": failed_sources[:50],
    }
    logger.info("poll_cycle_complete", **{k: v for k, v in summary.items() if k != "event"})

    # After first-run auto-poll, rebuild graph edges once (nodes already seeded).
    from src.workers import startup as startup_mod

    if startup_mod.needs_graph_after_first_poll and succeeded > 0:
        startup_mod.needs_graph_after_first_poll = False
        from src.workers.graph_builder import build_graph_relationships

        build_graph_relationships.delay()
        logger.info("first_poll_graph_rebuild_enqueued")

    return summary
