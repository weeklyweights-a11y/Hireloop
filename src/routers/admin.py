from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.deps import require_admin_key
from src.models import JobSourceConfig, PollLog, Stats
from src.models.database import get_db
from src.workers.cleanup_task import cleanup_old_closed_jobs
from src.workers.graph_builder import build_graph_relationships
from src.workers.poll_task import poll_all_sources
from src.workers.stats_task import update_stats

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin_key)],
)

STALE_AFTER = timedelta(hours=3)
POLL_INTERVAL = timedelta(hours=2)


class SourceCreate(BaseModel):
    company_name: str
    company_slug: str
    ats_type: str
    api_endpoint: str
    field_mapping: dict = Field(default_factory=dict)
    api_method: str = "GET"
    api_headers: dict = Field(default_factory=dict)
    api_params: dict = Field(default_factory=dict)
    api_body: dict | None = None
    response_path: str | None = None
    pagination_config: dict = Field(default_factory=dict)
    polling_interval_hours: int = 2
    active: bool = True


class SourceUpdate(BaseModel):
    company_name: str | None = None
    ats_type: str | None = None
    api_endpoint: str | None = None
    field_mapping: dict | None = None
    api_method: str | None = None
    api_headers: dict | None = None
    api_params: dict | None = None
    api_body: dict | None = None
    response_path: str | None = None
    pagination_config: dict | None = None
    polling_interval_hours: int | None = None
    active: bool | None = None


@router.post("/poll")
async def trigger_poll() -> dict:
    task = poll_all_sources.delay()
    return {
        "task_id": task.id,
        "message": "Poll triggered. Check /admin/poll/status for progress.",
    }


@router.post("/cleanup")
async def trigger_cleanup() -> dict:
    task = cleanup_old_closed_jobs.delay()
    return {"task_id": task.id, "message": "Cleanup triggered."}


@router.post("/stats")
async def trigger_stats() -> dict:
    task = update_stats.delay()
    return {"task_id": task.id, "message": "Stats refresh triggered."}


@router.post("/build-graph")
async def trigger_build_graph() -> dict:
    task = build_graph_relationships.delay()
    return {"task_id": task.id, "message": "Graph rebuild triggered."}


@router.post("/graph/rebuild")
async def trigger_graph_rebuild() -> dict:
    """OSS alias for POST /admin/build-graph."""
    return await trigger_build_graph()


@router.get("/poll/status")
async def poll_status(db: AsyncSession = Depends(get_db)) -> dict:
    latest = await db.scalar(select(func.max(PollLog.polled_at)))

    last_poll = None
    if latest is not None:
        window_start = latest - POLL_INTERVAL
        row = (
            await db.execute(
                select(
                    func.min(PollLog.polled_at),
                    func.max(PollLog.polled_at),
                    func.count(),
                    func.sum(case((PollLog.status == "success", 1), else_=0)),
                    func.sum(PollLog.jobs_found),
                    func.sum(PollLog.jobs_new),
                    func.sum(PollLog.jobs_updated),
                    func.sum(PollLog.jobs_closed),
                ).where(PollLog.polled_at > window_start)
            )
        ).one()
        started, completed, polled, succeeded, found, new, updated, closed = row
        last_poll = {
            "started_at": started.isoformat(),
            "completed_at": completed.isoformat(),
            "duration_minutes": round((completed - started).total_seconds() / 60, 1),
            "sources_polled": polled,
            "sources_succeeded": int(succeeded or 0),
            "sources_failed": polled - int(succeeded or 0),
            "total_jobs_found": int(found or 0),
            "new_jobs": int(new or 0),
            "updated_jobs": int(updated or 0),
            "closed_jobs": int(closed or 0),
        }

    stats = (await db.scalars(select(Stats))).first()
    now = datetime.now(UTC)

    warning = None
    last_full_poll = stats.last_full_poll_at if stats else None
    if last_full_poll is None or now - last_full_poll > STALE_AFTER:
        warning = "Last poll was over 3 hours ago. The scheduler may not be running."

    next_even_hour = (now.hour // 2 + 1) * 2
    next_poll = (
        (now + timedelta(hours=next_even_hour - now.hour)).replace(
            hour=next_even_hour % 24, minute=0, second=0, microsecond=0
        )
        if next_even_hour < 24
        else (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    )

    return {
        "last_poll": last_poll,
        "next_poll": next_poll.isoformat(),
        "warning": warning,
        "stats": {
            "total_active_jobs": stats.total_active_jobs if stats else 0,
            "total_companies": stats.total_companies if stats else 0,
            "total_cities": stats.total_cities if stats else 0,
        },
    }


def _source_dict(c: JobSourceConfig) -> dict:
    return {
        "id": str(c.id),
        "company_name": c.company_name,
        "company_slug": c.company_slug,
        "ats_type": c.ats_type,
        "api_endpoint": c.api_endpoint,
        "active": c.active,
        "last_polled_at": c.last_polled_at.isoformat() if c.last_polled_at else None,
        "last_success_at": c.last_success_at.isoformat() if c.last_success_at else None,
        "last_error": c.last_error,
        "total_jobs_found": c.total_jobs_found or 0,
        "polling_interval_hours": c.polling_interval_hours,
    }


@router.get("/sources")
async def list_sources(
    sort: str = "name",
    active: str = "all",
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(JobSourceConfig)
    if active == "true":
        stmt = stmt.where(JobSourceConfig.active.is_(True))
    elif active == "false":
        stmt = stmt.where(JobSourceConfig.active.is_(False))
    if sort == "error":
        stmt = stmt.order_by(JobSourceConfig.last_error.desc().nullslast())
    elif sort == "jobs":
        stmt = stmt.order_by(JobSourceConfig.total_jobs_found.desc().nullslast())
    else:
        stmt = stmt.order_by(JobSourceConfig.company_name.asc())
    rows = (await db.scalars(stmt)).all()
    return {"sources": [_source_dict(r) for r in rows], "count": len(rows)}


@router.get("/sources/{source_id}")
async def get_source(source_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    config = await db.get(JobSourceConfig, source_id)
    if config is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Source not found")
    logs = (
        await db.scalars(
            select(PollLog)
            .where(PollLog.source_config_id == source_id)
            .order_by(PollLog.polled_at.desc())
            .limit(10)
        )
    ).all()
    return {
        **_source_dict(config),
        "field_mapping": config.field_mapping,
        "api_method": config.api_method,
        "api_headers": config.api_headers,
        "api_params": config.api_params,
        "pagination_config": config.pagination_config,
        "recent_poll_logs": [
            {
                "polled_at": lg.polled_at.isoformat() if lg.polled_at else None,
                "status": lg.status,
                "jobs_found": lg.jobs_found,
                "error": lg.error_message,
            }
            for lg in logs
        ],
    }


@router.post("/sources")
async def create_source(body: SourceCreate, db: AsyncSession = Depends(get_db)) -> dict:
    config = JobSourceConfig(
        company_name=body.company_name,
        company_slug=body.company_slug,
        ats_type=body.ats_type,
        api_endpoint=body.api_endpoint,
        field_mapping=body.field_mapping,
        api_method=body.api_method,
        api_headers=body.api_headers,
        api_params=body.api_params,
        api_body=body.api_body,
        response_path=body.response_path,
        pagination_config=body.pagination_config,
        polling_interval_hours=body.polling_interval_hours,
        active=body.active,
    )
    db.add(config)
    await db.flush()
    return _source_dict(config)


@router.put("/sources/{source_id}")
async def update_source(
    source_id: UUID, body: SourceUpdate, db: AsyncSession = Depends(get_db)
) -> dict:
    config = await db.get(JobSourceConfig, source_id)
    if config is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Source not found")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(config, k, v)
    await db.flush()
    return _source_dict(config)


@router.delete("/sources/{source_id}")
async def deactivate_source(source_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    config = await db.get(JobSourceConfig, source_id)
    if config is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Source not found")
    config.active = False
    await db.flush()
    return _source_dict(config)


@router.patch("/sources/{source_id}/toggle")
async def toggle_source(source_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    config = await db.get(JobSourceConfig, source_id)
    if config is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Source not found")
    config.active = not bool(config.active)
    await db.flush()
    return _source_dict(config)


@router.post("/sources/{source_id}/test")
async def test_source(source_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    import asyncio

    config = await db.get(JobSourceConfig, source_id)
    if config is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Source not found")

    slug = config.company_slug

    def _run() -> dict:
        from src.models import get_sync_db
        from src.services.poller import poll_source

        with get_sync_db() as sync_db:
            row = sync_db.scalars(
                select(JobSourceConfig).where(JobSourceConfig.company_slug == slug)
            ).first()
            if row is None:
                return {"status": "error", "error": "Source not found in sync session"}
            result = poll_source(row, sync_db)
            return {
                "status": result.status,
                "jobs_found": result.jobs_found,
                "jobs_new": result.jobs_new,
                "jobs_updated": result.jobs_updated,
                "jobs_closed": result.jobs_closed,
                "error": result.error,
            }

    return await asyncio.to_thread(_run)
