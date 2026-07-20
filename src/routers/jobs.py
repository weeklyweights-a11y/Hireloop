from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.errors import InvalidRequestError
from src.models.database import get_db
from src.schemas.jobs import JobSearchFilters
from src.schemas.matching import MatchFilters
from src.services import job_service
from src.services.matching.matcher import match_jobs as run_match
from src.services.matching.response_tiers import apply_detail_tier, maybe_truncate

router = APIRouter(tags=["jobs"])


def _to_int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _to_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    return value.lower() in {"1", "true", "yes"}


def _skills(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [s.strip() for s in value.split(",") if s.strip()]


class MatchJobsBody(BaseModel):
    skills: list[str] = Field(default_factory=list)
    target_role: str | None = None
    location: str | None = None
    remote_ok: bool = True
    experience_years: int | None = None
    salary_min: int | None = None
    visa_needed: bool = False
    seniority: str | None = None
    companies: list[str] | None = None
    posted_within_hours: int | None = None
    limit: int = 20
    offset: int = 0
    detail: str = "full"


@router.get("/jobs/search")
async def search_jobs(
    q: str | None = Query(default=None),
    query: str | None = Query(default=None),
    location: str | None = Query(default=None),
    country: str | None = Query(default=None),
    company: str | None = Query(default=None),
    remote: str | None = Query(default=None),
    salary_min: str | None = Query(default=None),
    experience_max: str | None = Query(default=None),
    seniority: str | None = Query(default=None),
    visa_sponsorship: str | None = Query(default=None),
    employment_type: str | None = Query(default=None),
    skills: str | None = Query(default=None),
    my_skills: str | None = Query(default=None),
    posted_within_hours: str | None = Query(default=None),
    sort: str = Query(default="newest"),
    limit: str | None = Query(default=None),
    offset: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    filters = JobSearchFilters(
        query=query or q,
        location=location,
        country=country,
        company=company,
        remote=remote,
        salary_min=_to_int(salary_min),
        experience_max=_to_int(experience_max),
        seniority=seniority,
        visa_sponsorship=_to_bool(visa_sponsorship),
        employment_type=employment_type,
        skills=_skills(skills),
        my_skills=_skills(my_skills),
        posted_within_hours=_to_int(posted_within_hours),
        sort=sort,
        limit=_to_int(limit) or 20,
        offset=_to_int(offset) or 0,
    )
    result = await db.run_sync(lambda s: job_service.search_jobs(s, filters))
    return result.model_dump()


@router.post("/jobs/match")
async def match_jobs_endpoint(
    body: MatchJobsBody, db: AsyncSession = Depends(get_db)
) -> dict:
    skill_list = [s.strip() for s in body.skills if s and str(s).strip()]
    if not skill_list:
        raise InvalidRequestError(
            "skills is required (list of skills from your resume)."
        )
    filters = MatchFilters(
        target_role=body.target_role,
        location=body.location,
        remote_ok=body.remote_ok,
        experience_years=body.experience_years,
        salary_min=body.salary_min,
        visa_needed=body.visa_needed,
        seniority=body.seniority,
        companies=body.companies or None,
        posted_within_hours=body.posted_within_hours,
        limit=body.limit,
        offset=body.offset or 0,
    )

    def _run(session):
        result = run_match(session, skill_list, filters)
        payload = result.model_dump()
        payload["your_profile"] = payload.pop("profile_summary", {})
        payload = apply_detail_tier(payload, body.detail or "full")
        return maybe_truncate(payload)

    return await db.run_sync(_run)


@router.get("/jobs/companies")
async def list_companies(
    sort: str = Query(default="job_count"),
    limit: str | None = Query(default=None),
    offset: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows = await db.run_sync(
        lambda s: job_service.list_companies(
            s, sort=sort, limit=_to_int(limit) or 50, offset=_to_int(offset) or 0
        )
    )
    return {"companies": [r.model_dump() for r in rows]}


@router.get("/jobs/companies/{company}/insights")
async def company_insights(company: str, db: AsyncSession = Depends(get_db)) -> dict:
    from src.graph.insights import get_company_stack

    return await db.run_sync(lambda s: get_company_stack(s, company))


@router.get("/jobs/companies/{company}")
async def company_jobs(
    company: str,
    department: str | None = Query(default=None),
    seniority: str | None = Query(default=None),
    sort: str = Query(default="newest"),
    limit: str | None = Query(default=None),
    offset: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.run_sync(
        lambda s: job_service.get_company_jobs(
            s,
            company,
            department=department,
            seniority=seniority,
            sort=sort,
            limit=_to_int(limit) or 50,
            offset=_to_int(offset) or 0,
        )
    )
    return result.model_dump()


@router.get("/jobs/new")
async def get_new_jobs(
    since_hours: str | None = Query(default=None),
    q: str | None = Query(default=None),
    location: str | None = Query(default=None),
    company: str | None = Query(default=None),
    limit: str | None = Query(default=None),
    offset: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.run_sync(
        lambda s: job_service.get_new_jobs(
            s,
            since_hours=_to_int(since_hours) or 24,
            query=q,
            location=location,
            company=company,
            limit=_to_int(limit) or 20,
            offset=_to_int(offset) or 0,
        )
    )
    return result.model_dump()


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    detail = await db.run_sync(lambda s: job_service.get_job_detail(s, job_id))
    return detail.model_dump()


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)) -> dict:
    stats = await db.run_sync(job_service.get_platform_stats)
    return stats.model_dump()
