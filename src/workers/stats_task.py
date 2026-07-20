from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from src.models import Job, Stats, get_sync_db
from src.workers.celery_app import celery_app

logger = structlog.get_logger()


def refresh_stats(db: Session, last_full_poll_at: datetime | None = None) -> Stats:
    """Recompute and upsert the single stats row."""
    active = Job.status == "active"
    total_active = db.scalar(select(func.count()).select_from(Job).where(active))
    total_companies = db.scalar(select(func.count(func.distinct(Job.company_name))).where(active))
    total_cities = db.scalar(
        select(func.count(func.distinct(Job.location_city))).where(
            active, Job.location_city.is_not(None)
        )
    )
    added_24h = db.scalar(
        select(func.count())
        .select_from(Job)
        .where(active, Job.first_seen_at > text("NOW() - INTERVAL '24 hours'"))
    )
    closed_24h = db.scalar(
        select(func.count())
        .select_from(Job)
        .where(Job.status == "closed", Job.closed_at > text("NOW() - INTERVAL '24 hours'"))
    )

    stats = db.scalars(select(Stats)).first()
    if stats is None:
        stats = Stats()
        db.add(stats)
    stats.total_active_jobs = total_active
    stats.total_companies = total_companies
    stats.total_cities = total_cities
    stats.jobs_added_last_24h = added_24h
    stats.jobs_closed_last_24h = closed_24h
    stats.updated_at = datetime.now(UTC)
    if last_full_poll_at is not None:
        stats.last_full_poll_at = last_full_poll_at
    return stats


@celery_app.task(name="src.workers.stats_task.update_stats")
def update_stats() -> dict:
    with get_sync_db() as db:
        stats = refresh_stats(db)
        result = {
            "total_active_jobs": stats.total_active_jobs,
            "total_companies": stats.total_companies,
            "total_cities": stats.total_cities,
        }
    logger.info("stats_updated", **result)
    return result
