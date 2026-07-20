from celery import Celery

from src.config import settings
from src.workers.schedules import CELERY_BEAT_SCHEDULE

celery_app = Celery(
    "hireloop",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "src.workers.poll_task",
        "src.workers.stats_task",
        "src.workers.cleanup_task",
        "src.workers.graph_builder",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    beat_schedule=CELERY_BEAT_SCHEDULE,
)

# Register worker_ready auto-poll (import for side effect).
import src.workers.startup  # noqa: E402, F401
