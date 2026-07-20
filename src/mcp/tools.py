"""MCP tool wrappers around job_service."""

from __future__ import annotations

from src.models import get_sync_db
from src.schemas.jobs import JobSearchFilters
from src.services import job_service
from src.services.setup_status import FIRST_POLL_MESSAGE, first_poll_in_progress

NO_RESULTS_MESSAGE = (
    "No jobs matched your filters. Try a broader location, fewer constraints, "
    "or ask get_new_jobs for recent postings."
)


def _skills_list(skills: str | None) -> list[str] | None:
    if not skills:
        return None
    return [s.strip() for s in skills.split(",") if s.strip()]


def _with_empty_message(payload: dict, empty_key: str = "jobs") -> dict:
    """Attach setup or no-results message when list payloads are empty."""
    items = payload.get(empty_key)
    empty = items is None or items == [] or items == 0
    if not empty:
        return payload
    if first_poll_in_progress():
        return {**payload, "message": FIRST_POLL_MESSAGE}
    return {**payload, "message": NO_RESULTS_MESSAGE}


def tool_search_jobs(
    query: str | None = None,
    location: str | None = None,
    country: str | None = None,
    company: str | None = None,
    remote: str | None = None,
    experience_max: int | None = None,
    salary_min: int | None = None,
    seniority: str | None = None,
    visa_sponsorship: bool | None = None,
    employment_type: str | None = None,
    skills: str | None = None,
    my_skills: str | None = None,
    posted_within_hours: int | None = None,
    sort: str = "newest",
    limit: int = 20,
    offset: int = 0,
) -> dict:
    filters = JobSearchFilters(
        query=query,
        location=location,
        country=country,
        company=company,
        remote=remote,
        experience_max=experience_max,
        salary_min=salary_min,
        seniority=seniority,
        visa_sponsorship=visa_sponsorship,
        employment_type=employment_type,
        skills=_skills_list(skills),
        my_skills=_skills_list(my_skills),
        posted_within_hours=posted_within_hours,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    with get_sync_db() as db:
        payload = job_service.search_jobs(db, filters).model_dump()
    return _with_empty_message(payload, "jobs")


def tool_get_job_details(job_id: str) -> dict:
    with get_sync_db() as db:
        return job_service.get_job_detail(db, job_id).model_dump()


def tool_list_companies(
    sort: str = "job_count", limit: int = 50, offset: int = 0
) -> dict:
    with get_sync_db() as db:
        rows = job_service.list_companies(db, sort=sort, limit=limit, offset=offset)
        payload = {"companies": [r.model_dump() for r in rows]}
    return _with_empty_message(payload, "companies")


def tool_get_company_jobs(
    company: str,
    department: str | None = None,
    seniority: str | None = None,
    sort: str = "newest",
    limit: int = 50,
    offset: int = 0,
) -> dict:
    with get_sync_db() as db:
        payload = job_service.get_company_jobs(
            db,
            company=company,
            department=department,
            seniority=seniority,
            sort=sort,
            limit=limit,
            offset=offset,
        ).model_dump()
    return _with_empty_message(payload, "jobs")


def tool_get_stats() -> dict:
    with get_sync_db() as db:
        payload = job_service.get_platform_stats(db).model_dump()
    if first_poll_in_progress():
        payload = {**payload, "message": FIRST_POLL_MESSAGE}
    return payload

def tool_get_role_insights(role: str) -> dict:
    from src.errors import HireLoopError
    from src.graph import insights as graph_insights

    try:
        with get_sync_db() as db:
            return graph_insights.get_role_insights(db, role)
    except HireLoopError as exc:
        return {"error": exc.detail, "error_code": exc.error_code}


def tool_get_skill_insights(skill: str) -> dict:
    from src.errors import HireLoopError
    from src.graph import insights as graph_insights

    try:
        with get_sync_db() as db:
            return graph_insights.get_skill_insights(db, skill)
    except HireLoopError as exc:
        return {"error": exc.detail, "error_code": exc.error_code}


def tool_get_company_stack(company: str) -> dict:
    from src.errors import HireLoopError
    from src.graph import insights as graph_insights

    try:
        with get_sync_db() as db:
            return graph_insights.get_company_stack(db, company)
    except HireLoopError as exc:
        return {"error": exc.detail, "error_code": exc.error_code}


def tool_get_new_jobs(
    since_hours: int = 24,
    query: str | None = None,
    location: str | None = None,
    company: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    with get_sync_db() as db:
        payload = job_service.get_new_jobs(
            db,
            since_hours=since_hours,
            query=query,
            location=location,
            company=company,
            limit=limit,
            offset=offset,
        ).model_dump()
    return _with_empty_message(payload, "jobs")


def tool_match_jobs(
    skills: str,
    target_role: str | None = None,
    location: str | None = None,
    remote_ok: bool = True,
    experience_years: int | None = None,
    salary_min: int | None = None,
    visa_needed: bool = False,
    seniority: str | None = None,
    companies: str | None = None,
    posted_within_hours: int | None = None,
    limit: int = 20,
    offset: int = 0,
    detail: str = "summary",
) -> dict:
    from src.errors import InvalidRequestError
    from src.schemas.matching import MatchFilters
    from src.services.matching.matcher import match_jobs as run_match

    skill_list = _skills_list(skills) or []
    if not skill_list:
        err = InvalidRequestError(
            detail="skills is required (comma-separated list from your resume)."
        )
        return {"error": err.detail, "error_code": err.error_code}

    company_list = _skills_list(companies)
    filters = MatchFilters(
        target_role=target_role,
        location=location,
        remote_ok=remote_ok,
        experience_years=experience_years,
        salary_min=salary_min,
        visa_needed=visa_needed,
        seniority=seniority,
        companies=company_list,
        posted_within_hours=posted_within_hours,
        limit=limit,
        offset=offset,
    )
    with get_sync_db() as db:
        result = run_match(db, skill_list, filters)
    payload = result.model_dump()
    payload["your_profile"] = payload.pop("profile_summary", {})
    from src.services.matching.response_tiers import apply_detail_tier, maybe_truncate

    payload = apply_detail_tier(payload, detail)
    payload = maybe_truncate(payload)
    if first_poll_in_progress() and result.total_matches == 0:
        payload["message"] = FIRST_POLL_MESSAGE
    elif result.total_matches == 0:
        payload["message"] = NO_RESULTS_MESSAGE
    return payload


def tool_analyze_skills(skills: str) -> dict:
    from src.errors import InvalidRequestError
    from src.services.matching.analyze import analyze_skills

    skill_list = _skills_list(skills) or []
    if not skill_list:
        err = InvalidRequestError(detail="skills is required.")
        return {"error": err.detail, "error_code": err.error_code}
    with get_sync_db() as db:
        return analyze_skills(db, skill_list)


def tool_get_skill_gaps(skills: str, target_role: str) -> dict:
    from src.errors import InvalidRequestError
    from src.services.matching.analyze import get_skill_gaps

    skill_list = _skills_list(skills) or []
    if not skill_list or not (target_role or "").strip():
        err = InvalidRequestError(detail="skills and target_role are required.")
        return {"error": err.detail, "error_code": err.error_code}
    with get_sync_db() as db:
        return get_skill_gaps(db, skill_list, target_role.strip())


def tool_create_watch(
    skills: str | None = None,
    target_role: str | None = None,
    companies: str | None = None,
    location: str | None = None,
    remote_ok: bool = True,
    salary_min: int | None = None,
) -> dict:
    from datetime import UTC, datetime

    from src.schemas.jobs import JobSearchFilters
    from src.schemas.matching import MatchFilters
    from src.services.matching.matcher import match_jobs as run_match

    skill_list = _skills_list(skills)
    company_list = _skills_list(companies)
    config = {
        "skills": skill_list or [],
        "target_role": target_role,
        "companies": company_list or [],
        "location": location,
        "remote_ok": remote_ok,
        "salary_min": salary_min,
    }
    with get_sync_db() as db:
        if skill_list:
            result = run_match(
                db,
                skill_list,
                MatchFilters(
                    target_role=target_role,
                    location=location,
                    remote_ok=remote_ok,
                    salary_min=salary_min,
                    companies=company_list,
                    limit=50,
                ),
            )
            count = result.total_matches
        else:
            filters = JobSearchFilters(
                location=location,
                company=(company_list[0] if company_list and len(company_list) == 1 else None),
                salary_min=salary_min,
                query=target_role,
                remote="remote" if remote_ok is False else None,
                limit=1,
            )
            # For multi-company without skills, count via successive filters
            if company_list and len(company_list) > 1:
                count = 0
                for co in company_list:
                    r = job_service.search_jobs(
                        db, JobSearchFilters(company=co, location=location, query=target_role, limit=1)
                    )
                    count += r.total_results
            else:
                count = job_service.search_jobs(db, filters).total_results

    return {
        "watch_config": config,
        "current_snapshot": {
            "matching_jobs_now": count,
            "as_of": datetime.now(UTC).isoformat(),
        },
        "instructions_for_client": (
            "Store this config. To check for new jobs, call match_jobs or search_jobs "
            "with these parameters plus posted_within_hours=4 (one poll cycle). "
            "New jobs since the snapshot will appear in the results."
        ),
    }
