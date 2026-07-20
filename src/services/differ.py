from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models import Job, JobSourceConfig
from src.services.dedup import check_duplicate
from src.services.extractors.html import normalize_for_comparison
from src.services.field_mapper import MappedJob
from src.services.parser import ParsedJob, parse_job

CLOSE_AFTER_MISSES = 2

_MAX_LEN = {
    "source_job_id": 255,
    "title_raw": 500,
    "title_normalized": 255,
    "department": 255,
    "location_city": 100,
    "location_state": 50,
    "location_country": 10,
    "location_metro": 100,
    "apply_url": 1000,
}


def _clip(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    return value[: _MAX_LEN[field]]


def _apply_parsed(job: Job, parsed: ParsedJob) -> None:
    job.location_city = _clip(parsed.location_city, "location_city")
    job.location_state = _clip(parsed.location_state, "location_state")
    job.location_country = _clip(parsed.location_country, "location_country")
    job.location_metro = _clip(parsed.location_metro, "location_metro")
    job.remote_policy = parsed.remote_policy
    job.salary_min = parsed.salary_min
    job.salary_max = parsed.salary_max
    job.experience_min = parsed.experience_min
    job.experience_max = parsed.experience_max
    job.title_normalized = _clip(parsed.title_normalized, "title_normalized")
    job.title_metadata = parsed.title_metadata
    if not job.department and parsed.title_department:
        job.department = _clip(parsed.title_department, "department")
    job.seniority = parsed.seniority
    job.employment_type = parsed.employment_type
    job.visa_sponsorship = parsed.visa_sponsorship
    job.skills_required = parsed.skills_required
    job.skills_nice_to_have = parsed.skills_nice_to_have
    job.description_text = parsed.description_text
    job.description_html = parsed.description_html


class DiffResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    new_jobs: list[MappedJob]
    updated_jobs: list[tuple[MappedJob, Job]]
    missing_job_ids: list[str]
    present_job_ids: list[str]
    unchanged_count: int


class ApplyResult(BaseModel):
    jobs_inserted: int
    jobs_updated: int
    jobs_closed: int
    jobs_missing_grace: int
    jobs_unchanged: int


def diff_jobs(
    source_slug: str,
    source_ats: str,
    api_jobs: list[MappedJob],
    db_jobs: list[Job],
) -> DiffResult:
    db_by_id = {job.source_job_id: job for job in db_jobs}
    api_by_id = {job.id: job for job in api_jobs}

    new_jobs = [job for job_id, job in api_by_id.items() if job_id not in db_by_id]
    missing_job_ids = [job_id for job_id in db_by_id if job_id not in api_by_id]

    updated_jobs: list[tuple[MappedJob, Job]] = []
    present_job_ids: list[str] = []
    unchanged = 0
    for job_id, api_job in api_by_id.items():
        db_job = db_by_id.get(job_id)
        if db_job is None:
            continue
        present_job_ids.append(job_id)
        title_changed = normalize_for_comparison(api_job.title) != normalize_for_comparison(
            db_job.title_raw
        )
        desc_changed = normalize_for_comparison(api_job.description) != normalize_for_comparison(
            db_job.description_html
        )
        if title_changed or desc_changed:
            updated_jobs.append((api_job, db_job))
        else:
            unchanged += 1

    return DiffResult(
        new_jobs=new_jobs,
        updated_jobs=updated_jobs,
        missing_job_ids=missing_job_ids,
        present_job_ids=present_job_ids,
        unchanged_count=unchanged,
    )


def apply_diff(diff: DiffResult, source_config: JobSourceConfig, db_session: Session) -> ApplyResult:
    now = datetime.now(UTC)
    db_jobs = db_session.scalars(
        select(Job).where(Job.source_company_slug == source_config.company_slug)
    ).all()
    db_by_id = {job.source_job_id: job for job in db_jobs}

    for api_job in diff.new_jobs:
        parsed = parse_job(api_job.title, api_job.location, api_job.description)
        job = Job(
            source_company_slug=source_config.company_slug,
            source_ats=source_config.ats_type,
            source_job_id=_clip(api_job.id, "source_job_id"),
            source_url=source_config.company_website,
            apply_url=_clip(api_job.apply_url, "apply_url"),
            title_raw=_clip(api_job.title, "title_raw"),
            company_name=source_config.company_name,
            company_logo_url=source_config.company_logo_url,
            department=_clip(api_job.department, "department"),
            status="active",
            consecutive_misses=0,
            first_seen_at=now,
            last_verified_at=now,
        )
        _apply_parsed(job, parsed)
        db_session.add(job)
        db_session.flush()
        check_duplicate(job, db_session)

    for api_job, db_job in diff.updated_jobs:
        parsed = parse_job(api_job.title, api_job.location, api_job.description)
        db_job.title_raw = _clip(api_job.title, "title_raw")
        db_job.apply_url = _clip(api_job.apply_url, "apply_url")
        db_job.department = _clip(api_job.department, "department")
        _apply_parsed(db_job, parsed)
        db_job.updated_at = now
        db_job.last_verified_at = now
        db_job.consecutive_misses = 0
        if db_job.status == "closed":
            db_job.status = "active"
            db_job.closed_at = None

    closed = grace = 0
    updated_ids = {api_job.id for api_job, _ in diff.updated_jobs}
    for job_id in diff.missing_job_ids:
        db_job = db_by_id[job_id]
        # Only grace-close active rows; leave duplicate (and closed) alone
        if db_job.status != "active":
            continue
        db_job.consecutive_misses = (db_job.consecutive_misses or 0) + 1
        if db_job.consecutive_misses >= CLOSE_AFTER_MISSES:
            db_job.status = "closed"
            db_job.closed_at = now
            closed += 1
        else:
            grace += 1

    for job_id in diff.present_job_ids:
        if job_id in updated_ids:
            continue
        db_job = db_by_id[job_id]
        db_job.last_verified_at = now
        db_job.consecutive_misses = 0
        if db_job.status == "closed":
            db_job.status = "active"
            db_job.closed_at = None

    return ApplyResult(
        jobs_inserted=len(diff.new_jobs),
        jobs_updated=len(diff.updated_jobs),
        jobs_closed=closed,
        jobs_missing_grace=grace,
        jobs_unchanged=diff.unchanged_count,
    )
