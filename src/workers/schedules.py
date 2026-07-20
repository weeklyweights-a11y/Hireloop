from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "poll-all-sources": {
        "task": "src.workers.poll_task.poll_all_sources",
        "schedule": crontab(minute=0, hour="*/2"),  # every 2 hours: 00, 02, 04, ...
    },
    "update-stats": {
        "task": "src.workers.stats_task.update_stats",
        "schedule": crontab(minute=5, hour="*/2"),  # 5 min after each poll
    },
    "build-graph": {
        "task": "src.workers.graph_builder.build_graph_relationships",
        "schedule": crontab(minute=15, hour="*/2"),  # 15 min after each poll
    },
    "cleanup-closed-jobs": {
        "task": "src.workers.cleanup_task.cleanup_old_closed_jobs",
        "schedule": crontab(minute=0, hour=3),  # daily at 3 AM UTC
    },
}
