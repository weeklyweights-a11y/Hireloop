"""First-run setup status shared by /health and MCP empty-state messages."""

from __future__ import annotations

from sqlalchemy import func, select

from src.models import Job, JobSourceConfig, get_sync_db

FIRST_POLL_MESSAGE = (
    "HireLoop is loading jobs for the first time. This usually takes a few minutes. "
    "Check GET /health for setup progress, then try again."
)


def get_setup_status() -> dict:
    """Return OSS §2.3 setup block fields."""
    sources_configured = 0
    jobs_loaded = 0
    try:
        with get_sync_db() as db:
            sources_configured = (
                db.scalar(
                    select(func.count())
                    .select_from(JobSourceConfig)
                    .where(JobSourceConfig.active)
                )
                or 0
            )
            jobs_loaded = (
                db.scalar(
                    select(func.count()).select_from(Job).where(Job.status == "active")
                )
                or 0
            )
    except Exception:
        pass

    first_poll_complete = jobs_loaded > 0
    if sources_configured == 0:
        message = "Waiting for source configs to be seeded."
    elif not first_poll_complete:
        message = FIRST_POLL_MESSAGE
    else:
        message = "Ready."

    return {
        "sources_configured": sources_configured,
        "first_poll_complete": first_poll_complete,
        "jobs_loaded": jobs_loaded,
        "message": message,
    }


def first_poll_in_progress() -> bool:
    setup = get_setup_status()
    return setup["sources_configured"] > 0 and not setup["first_poll_complete"]
