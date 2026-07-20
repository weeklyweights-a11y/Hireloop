"""Celery worker_ready: wait for seeded sources, then auto-poll if DB is empty."""

from __future__ import annotations

import time

import structlog
from celery.signals import worker_ready
from sqlalchemy import func, select

from src.models import Job, JobSourceConfig, get_sync_db

logger = structlog.get_logger()

# Set True when we enqueue the first empty-DB poll; poll_task clears after enqueueing graph.
needs_graph_after_first_poll = False

_SOURCE_WAIT_SECONDS = 60
_SOURCE_POLL_INTERVAL = 2


def _count_active_sources() -> int:
    with get_sync_db() as db:
        return (
            db.scalar(
                select(func.count())
                .select_from(JobSourceConfig)
                .where(JobSourceConfig.active)
            )
            or 0
        )


def _count_active_jobs() -> int:
    with get_sync_db() as db:
        return (
            db.scalar(select(func.count()).select_from(Job).where(Job.status == "active"))
            or 0
        )


def wait_for_sources(timeout: float = _SOURCE_WAIT_SECONDS) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            n = _count_active_sources()
            if n > 0:
                return n
        except Exception as exc:
            logger.warning("wait_for_sources_error", error=str(exc))
        time.sleep(_SOURCE_POLL_INTERVAL)
    return _count_active_sources()


@worker_ready.connect
def on_worker_ready(**_kwargs) -> None:
    global needs_graph_after_first_poll

    sources = wait_for_sources()
    if sources == 0:
        logger.warning("startup_no_sources", waited_seconds=_SOURCE_WAIT_SECONDS)
        return

    jobs = _count_active_jobs()
    if jobs > 0:
        logger.info("startup_skip_poll", active_jobs=jobs, sources=sources)
        return

    from src.workers.poll_task import poll_all_sources

    needs_graph_after_first_poll = True
    poll_all_sources.delay()
    logger.info("startup_first_poll_enqueued", sources=sources)
