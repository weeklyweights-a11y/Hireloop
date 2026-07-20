import structlog
from sqlalchemy import text

from src.models import get_sync_db
from src.workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(name="src.workers.cleanup_task.cleanup_old_closed_jobs")
def cleanup_old_closed_jobs() -> dict:
    with get_sync_db() as db:
        jobs_deleted = db.execute(
            text("DELETE FROM jobs WHERE status = 'closed' AND closed_at < NOW() - INTERVAL '7 days'")
        ).rowcount
        logs_deleted = db.execute(
            text("DELETE FROM poll_logs WHERE polled_at < NOW() - INTERVAL '14 days'")
        ).rowcount
    logger.info("cleanup_complete", jobs_deleted=jobs_deleted, poll_logs_deleted=logs_deleted)
    return {"jobs_deleted": jobs_deleted, "poll_logs_deleted": logs_deleted}
