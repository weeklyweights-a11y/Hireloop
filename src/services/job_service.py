from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from src.errors import JobNotFoundError
from src.graph.connection import is_available, sync_session
from src.graph.queries import expand_roles, expand_skills, role_insights_for_title
from src.models import Job, Stats
from src.schemas.jobs import (
    CompanyJobsResult,
    CompanySummary,
    JobDetail,
    JobSearchFilters,
    JobSearchResult,
    JobSummary,
    PlatformStats,
    format_ago,
)
from src.services.data_loader import DataLoader
from src.services.extractors.title import normalize_title


def _location_label(job: Job) -> str | None:
    parts = [p for p in (job.location_city, job.location_state) if p]
    if parts:
        return ", ".join(parts)
    if job.remote_policy == "remote":
        return "Remote"
    return None


def _salary_range(job: Job) -> str | None:
    if job.salary_min is None and job.salary_max is None:
        return None
    if job.salary_min is not None and job.salary_max is not None:
        return f"${job.salary_min:,} - ${job.salary_max:,}/year"
    if job.salary_min is not None:
        return f"${job.salary_min:,}+/year"
    return f"up to ${job.salary_max:,}/year"


def _experience_label(job: Job) -> str | None:
    if job.experience_min is None and job.experience_max is None:
        return None
    if job.experience_min is not None and job.experience_max is not None:
        return f"{job.experience_min}-{job.experience_max} years"
    if job.experience_min is not None:
        return f"{job.experience_min}+ years"
    return f"up to {job.experience_max} years"


def job_to_summary(
    job: Job,
    relevance_score: int | None = None,
    match_type: str | None = None,
    role_insights: dict | None = None,
    quick_match: int | None = None,
) -> JobSummary:
    return JobSummary(
        id=str(job.id),
        title=job.title_raw,
        title_normalized=job.title_normalized,
        company=job.company_name,
        location=_location_label(job),
        location_city=job.location_city,
        location_state=job.location_state,
        location_country=job.location_country,
        location_metro=job.location_metro,
        remote_policy=job.remote_policy,
        seniority=job.seniority,
        employment_type=job.employment_type,
        salary_range=_salary_range(job),
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        experience=_experience_label(job),
        experience_min=job.experience_min,
        experience_max=job.experience_max,
        skills_required=list(job.skills_required or []),
        skills_nice_to_have=list(job.skills_nice_to_have or []),
        skills_implied=list(job.skills_implied or []),
        visa_sponsorship=job.visa_sponsorship,
        department=job.department,
        apply_url=job.apply_url,
        first_seen=job.first_seen_at.isoformat() if job.first_seen_at else None,
        last_verified=job.last_verified_at.isoformat() if job.last_verified_at else None,
        freshness=format_ago(job.last_verified_at or job.first_seen_at),
        relevance_score=relevance_score,
        match_type=match_type,
        role_insights=role_insights,
        quick_match=quick_match,
    )


def job_to_detail(job: Job, market_context: dict | None = None) -> JobDetail:
    base = job_to_summary(job)
    return JobDetail(
        **base.model_dump(),
        description_text=job.description_text,
        description_html=job.description_html,
        source_ats=job.source_ats,
        source_company_slug=job.source_company_slug,
        source_url=job.source_url,
        status=job.status,
        market_context=market_context,
    )


def _resolve_location_filter(
    location: str, data: dict
) -> tuple[str | None, str | None, bool, str | None]:
    """Return (city, metro, is_remote, country_code)."""
    raw = location.strip()
    lower = raw.lower()
    if lower == "remote":
        return (None, None, True, None)
    if lower in {"us", "usa", "u.s.", "u.s.a.", "united states", "united states of america", "america"}:
        return (None, None, False, "US")

    aliases = {k.lower(): v for k, v in data.get("city_aliases", {}).items()}
    city = aliases.get(lower, raw)
    metro = None
    if lower in {"bay area", "silicon valley"}:
        metro = "San Francisco"
        city = "San Francisco"
    else:
        for metro_name, cities in data.get("metro_areas", {}).items():
            if city.lower() == metro_name.lower():
                metro = metro_name
                break
    return (city, metro, False, None)


def _apply_job_filters(
    stmt,
    *,
    locations: dict,
    location: str | None = None,
    country: str | None = None,
    company: str | None = None,
    company_names: list[str] | None = None,
    remote: str | None = None,
    remote_ok: bool | None = None,
    experience_max: int | None = None,
    experience_years: int | None = None,
    salary_min: int | None = None,
    seniority: str | None = None,
    visa_sponsorship: bool | None = None,
    visa_needed: bool = False,
    employment_type: str | None = None,
    title_normalized_in: list[str] | None = None,
    skill_groups: list[list[str]] | None = None,
    skills: list[str] | None = None,
    posted_within_hours: int | None = None,
):
    """Shared SQL filters for search and match paths."""
    stmt = stmt.where(Job.status == "active")

    if location:
        city, metro, is_remote, loc_country = _resolve_location_filter(location, locations)
        if loc_country and not country:
            country = loc_country
        elif is_remote:
            stmt = stmt.where(Job.remote_policy == "remote")
        elif metro:
            stmt = stmt.where(
                or_(Job.location_metro == metro, Job.location_city.ilike(city))
            )
        elif city:
            stmt = stmt.where(
                or_(Job.location_city.ilike(city), Job.location_metro.ilike(city))
            )

    if country:
        stmt = stmt.where(Job.location_country == country.upper())

    if company:
        stmt = stmt.where(Job.company_name.ilike(f"%{company}%"))

    if company_names:
        stmt = stmt.where(Job.company_name.in_(company_names))

    if remote and remote != "any":
        stmt = stmt.where(Job.remote_policy == remote)

    if remote_ok is False:
        stmt = stmt.where(Job.remote_policy != "remote")

    exp_cap = experience_years if experience_years is not None else experience_max
    if exp_cap is not None:
        stmt = stmt.where(
            or_(Job.experience_min.is_(None), Job.experience_min <= exp_cap)
        )

    if salary_min is not None:
        stmt = stmt.where(
            or_(Job.salary_max.is_(None), Job.salary_max >= salary_min)
        )

    if seniority:
        stmt = stmt.where(Job.seniority == seniority)

    if visa_sponsorship is True or visa_needed:
        stmt = stmt.where(Job.visa_sponsorship == "sponsors")

    if employment_type:
        stmt = stmt.where(Job.employment_type == employment_type)

    if title_normalized_in:
        stmt = stmt.where(Job.title_normalized.in_(title_normalized_in))

    if skill_groups:
        for group in skill_groups:
            stmt = stmt.where(
                or_(
                    *[Job.skills_required.contains([s]) for s in group],
                    *[Job.skills_implied.contains([s]) for s in group],
                )
            )
    elif skills:
        stmt = stmt.where(Job.skills_required.contains(skills))

    if posted_within_hours is not None:
        cutoff = datetime.now(UTC) - timedelta(hours=posted_within_hours)
        stmt = stmt.where(Job.first_seen_at >= cutoff)

    return stmt


def _apply_filters(
    stmt,
    filters: JobSearchFilters,
    locations: dict,
    *,
    skill_groups: list[list[str]] | None = None,
    title_normalized_in: list[str] | None = None,
):
    return _apply_job_filters(
        stmt,
        locations=locations,
        location=filters.location,
        country=filters.country,
        company=filters.company,
        remote=filters.remote,
        experience_max=filters.experience_max,
        salary_min=filters.salary_min,
        seniority=filters.seniority,
        visa_sponsorship=filters.visa_sponsorship,
        employment_type=filters.employment_type,
        title_normalized_in=title_normalized_in,
        skill_groups=skill_groups,
        skills=filters.skills,
        posted_within_hours=filters.posted_within_hours,
    )


def _resolve_query_role(query: str, data: DataLoader) -> str | None:
    q = query.strip()
    if not q:
        return None
    canonical = data.title_alias_index.get(q.lower())
    if canonical:
        return canonical
    title, _fn = normalize_title(q, data.taxonomy)
    return title


def _resolve_skill_canonical(name: str, data: DataLoader) -> str:
    lower = name.strip().lower()
    for entry in data.skills:
        if entry["canonical"].lower() == lower:
            return entry["canonical"]
        for alias in entry.get("aliases") or []:
            if alias.lower() == lower:
                return entry["canonical"]
    return name.strip()


def _match_type_for_job(
    job: Job,
    *,
    canonical_role: str | None,
    similar_roles: set[str],
    requested_skills: list[str],
) -> str | None:
    title_mt = None
    if canonical_role:
        if job.title_normalized == canonical_role:
            title_mt = "direct"
        elif job.title_normalized in similar_roles:
            title_mt = "similar_role"

    skill_mt = None
    if requested_skills:
        req = set(job.skills_required or [])
        if any(s in req for s in requested_skills):
            skill_mt = "direct_skill"
        else:
            skill_mt = "implied_skill"

    if title_mt and skill_mt:
        # Prefer title match_type when both present; ranking handles combo
        return title_mt
    return title_mt or skill_mt


def _combo_rank(
    job: Job,
    *,
    canonical_role: str | None,
    similar_roles: set[str],
    requested_skills: list[str],
    base_score: int,
) -> int:
    """Higher is better — encodes the spec 4.5 ranking matrix."""
    direct_title = bool(canonical_role and job.title_normalized == canonical_role)
    similar_title = bool(
        canonical_role and job.title_normalized in similar_roles
    )
    direct_skill = False
    implied_skill = False
    if requested_skills:
        req = set(job.skills_required or [])
        impl = set(job.skills_implied or [])
        direct_skill = any(s in req for s in requested_skills)
        implied_skill = (not direct_skill) and any(
            s in req or s in impl for s in requested_skills
        )

    bonus = 0
    if direct_title and direct_skill:
        bonus = 100
    elif direct_title and implied_skill:
        bonus = 80
    elif similar_title and direct_skill:
        bonus = 60
    elif similar_title and implied_skill:
        bonus = 40
    elif direct_title:
        bonus = 50
    elif similar_title:
        bonus = 30
    elif direct_skill:
        bonus = 25
    elif implied_skill:
        bonus = 15
    return base_score + bonus


def _relevance_score_expr(query: str):
    q = query.strip()
    pattern = f"%{q}%"
    return (
        case((func.lower(Job.title_normalized) == q.lower(), 30), else_=0)
        + case(
            (Job.title_normalized.is_not(None) & Job.title_normalized.ilike(pattern), 20),
            else_=0,
        )
        + case((Job.title_raw.ilike(pattern), 15), else_=0)
        + case((Job.description_text.ilike(pattern), 5), else_=0)
    )


def _data_freshness(db: Session) -> str:
    newest = db.scalar(
        select(func.max(Job.last_verified_at)).where(Job.status == "active")
    )
    return format_ago(newest) if newest else "unknown"


def _quick_match_pct(job: Job, my_skills: list[str] | None) -> int | None:
    """Lightweight overlap vs skills_required only (spec §6.1)."""
    if not my_skills:
        return None
    data = DataLoader.get()
    mine = {_resolve_skill_canonical(s, data) for s in my_skills}
    required = list(job.skills_required or [])
    if not required:
        return 100
    hits = sum(1 for s in required if _resolve_skill_canonical(s, data) in mine)
    return int(round(100 * hits / len(required)))


def _market_context(db: Session, job: Job) -> dict | None:
    title = job.title_normalized
    if not title:
        return None
    role_demand = (
        db.scalar(
            select(func.count())
            .select_from(Job)
            .where(Job.status == "active", Job.title_normalized == title)
        )
        or 0
    )
    salary_percentile = None
    if job.salary_max is not None:
        peers = db.scalars(
            select(Job.salary_max).where(
                Job.status == "active",
                Job.title_normalized == title,
                Job.salary_max.is_not(None),
            )
        ).all()
        if peers:
            below = sum(1 for p in peers if p is not None and p <= job.salary_max)
            salary_percentile = int(round(100 * below / len(peers)))

    skill_rarity = None
    top_skill = (job.skills_required or [None])[0]
    if top_skill and is_available():
        data = DataLoader.get()
        skill_name = _resolve_skill_canonical(top_skill, data)
        try:
            with sync_session() as session:
                rec = session.run(
                    """
                    MATCH (:Role {title: $title})-[rel:NEEDS_SKILL]->(s:Skill {name: $skill})
                    RETURN rel.frequency AS freq
                    LIMIT 1
                    """,
                    title=title,
                    skill=skill_name,
                ).single()
                if rec and rec["freq"] is not None:
                    skill_rarity = float(rec["freq"])
        except Exception:
            skill_rarity = None

    week_ago = datetime.now(UTC) - timedelta(days=7)
    company_hiring_pace = (
        db.scalar(
            select(func.count())
            .select_from(Job)
            .where(
                Job.status == "active",
                Job.company_name == job.company_name,
                Job.first_seen_at >= week_ago,
            )
        )
        or 0
    )
    return {
        "role_demand": int(role_demand),
        "salary_percentile": salary_percentile,
        "skill_rarity": skill_rarity,
        "company_hiring_pace": int(company_hiring_pace),
    }


def search_jobs(db: Session, filters: JobSearchFilters) -> JobSearchResult:
    data = DataLoader.get()
    locations = data.locations
    limit = max(1, min(filters.limit, 50))
    offset = max(0, filters.offset)
    sort = filters.sort

    canonical_role: str | None = None
    similar_roles: list[str] = []
    title_normalized_in: list[str] | None = None
    use_text_query = False

    if filters.query:
        canonical_role = _resolve_query_role(filters.query, data)
        if canonical_role:
            similar_roles = expand_roles(canonical_role, min_overlap=0.6)
            title_normalized_in = [canonical_role, *similar_roles]
        else:
            use_text_query = True

    skill_groups: list[list[str]] | None = None
    requested_skills: list[str] = []
    if filters.skills:
        skill_groups = []
        for raw in filters.skills:
            canon = _resolve_skill_canonical(raw, data)
            requested_skills.append(canon)
            skill_groups.append(expand_skills(canon))

    similar_set = set(similar_roles)
    filter_kw = dict(
        skill_groups=skill_groups,
        title_normalized_in=title_normalized_in if not use_text_query else None,
    )

    if use_text_query and filters.query:
        score = _relevance_score_expr(filters.query)
        scored = _apply_filters(
            select(Job, score.label("relevance_score")),
            filters,
            locations,
            **filter_kw,
        ).where(score > 0)
        total = db.scalar(select(func.count()).select_from(scored.subquery())) or 0
        if sort == "salary_high":
            ordered = scored.order_by(Job.salary_max.desc().nullslast())
        elif sort == "salary_low":
            ordered = scored.order_by(Job.salary_min.asc().nullslast())
        elif sort == "newest":
            ordered = scored.order_by(Job.first_seen_at.desc())
        else:
            ordered = scored.order_by(score.desc(), Job.first_seen_at.desc())
        rows = db.execute(ordered.limit(limit).offset(offset)).all()
        jobs = []
        for job, sc in rows:
            insights = (
                role_insights_for_title(job.title_normalized)
                if job.title_normalized
                else None
            )
            jobs.append(
                job_to_summary(
                    job,
                    relevance_score=int(sc or 0),
                    match_type=None,
                    role_insights=insights,
                    quick_match=_quick_match_pct(job, filters.my_skills),
                )
            )
    else:
        base = _apply_filters(select(Job), filters, locations, **filter_kw)
        # Fetch a wider window then re-rank when graph expansion is active
        fetch_n = limit + offset
        if canonical_role or requested_skills:
            fetch_n = min(500, max(fetch_n * 3, limit + limit))
        if sort == "salary_high":
            ordered = base.order_by(Job.salary_max.desc().nullslast())
        elif sort == "salary_low":
            ordered = base.order_by(Job.salary_min.asc().nullslast())
        else:
            ordered = base.order_by(Job.first_seen_at.desc())

        if canonical_role or requested_skills:
            candidates = db.scalars(ordered.limit(fetch_n)).all()
            ranked = sorted(
                candidates,
                key=lambda j: _combo_rank(
                    j,
                    canonical_role=canonical_role,
                    similar_roles=similar_set,
                    requested_skills=requested_skills,
                    base_score=0,
                ),
                reverse=True,
            )
            total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
            page = ranked[offset : offset + limit]
            jobs = []
            for job in page:
                mt = _match_type_for_job(
                    job,
                    canonical_role=canonical_role,
                    similar_roles=similar_set,
                    requested_skills=requested_skills,
                )
                insights = (
                    role_insights_for_title(job.title_normalized)
                    if job.title_normalized
                    else None
                )
                jobs.append(
                    job_to_summary(
                        job,
                        relevance_score=_combo_rank(
                            job,
                            canonical_role=canonical_role,
                            similar_roles=similar_set,
                            requested_skills=requested_skills,
                            base_score=0,
                        ),
                        match_type=mt,
                        role_insights=insights,
                        quick_match=_quick_match_pct(job, filters.my_skills),
                    )
                )
        else:
            total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
            job_rows = db.scalars(ordered.limit(limit).offset(offset)).all()
            jobs = [
                job_to_summary(
                    j,
                    role_insights=(
                        role_insights_for_title(j.title_normalized)
                        if j.title_normalized
                        else None
                    ),
                    quick_match=_quick_match_pct(j, filters.my_skills),
                )
                for j in job_rows
            ]

    return JobSearchResult(
        total_results=total,
        showing=len(jobs),
        offset=offset,
        jobs=jobs,
        filters_applied=filters.model_dump(exclude_none=True),
        data_freshness=_data_freshness(db),
    )


def get_job_detail(db: Session, job_id: str) -> JobDetail:
    try:
        parsed = uuid.UUID(job_id)
    except ValueError as e:
        raise JobNotFoundError() from e
    job = db.get(Job, parsed)
    if job is None:
        raise JobNotFoundError()
    return job_to_detail(job, market_context=_market_context(db, job))


def list_companies(
    db: Session, sort: str = "job_count", limit: int = 50, offset: int = 0
) -> list[CompanySummary]:
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    stmt = (
        select(
            Job.company_name,
            func.count().label("active_jobs"),
            func.max(Job.first_seen_at).label("newest_job_at"),
        )
        .where(Job.status == "active")
        .group_by(Job.company_name)
    )
    if sort == "name":
        stmt = stmt.order_by(Job.company_name.asc())
    elif sort == "newest_job":
        stmt = stmt.order_by(func.max(Job.first_seen_at).desc().nullslast())
    else:
        stmt = stmt.order_by(func.count().desc(), Job.company_name.asc())

    rows = db.execute(stmt.limit(limit).offset(offset)).all()
    return [
        CompanySummary(
            company_name=r[0],
            active_jobs=int(r[1]),
            newest_job_at=r[2].isoformat() if r[2] else None,
        )
        for r in rows
    ]


def get_company_jobs(
    db: Session,
    company: str,
    department: str | None = None,
    seniority: str | None = None,
    sort: str = "newest",
    limit: int = 50,
    offset: int = 0,
) -> CompanyJobsResult:
    filters = JobSearchFilters(
        company=company,
        seniority=seniority,
        sort=sort if sort in {"newest", "salary_high", "salary_low"} else "newest",
        limit=limit,
        offset=offset,
    )
    result = search_jobs(db, filters)
    jobs = result.jobs
    if department:
        jobs = [j for j in jobs if (j.department or "").lower() == department.lower()]
    return CompanyJobsResult(
        company_name=company,
        active_jobs=result.total_results,
        jobs=jobs,
    )


def get_new_jobs(
    db: Session,
    since_hours: int = 24,
    query: str | None = None,
    location: str | None = None,
    company: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> JobSearchResult:
    return search_jobs(
        db,
        JobSearchFilters(
            query=query,
            location=location,
            company=company,
            posted_within_hours=since_hours,
            sort="newest",
            limit=limit,
            offset=offset,
        ),
    )


def get_platform_stats(db: Session) -> PlatformStats:
    from src.graph.insights import graph_stats_block

    stats = db.scalars(select(Stats)).first()
    top_companies = list_companies(db, sort="job_count", limit=10, offset=0)
    role_rows = db.execute(
        select(Job.title_normalized, func.count().label("c"))
        .where(Job.status == "active", Job.title_normalized.is_not(None))
        .group_by(Job.title_normalized)
        .order_by(func.count().desc())
        .limit(10)
    ).all()
    top_roles = [{"title": r[0], "count": int(r[1])} for r in role_rows]
    graph = graph_stats_block()

    if stats is None:
        return PlatformStats(
            top_companies=top_companies,
            top_roles=top_roles,
            data_freshness=_data_freshness(db),
            graph=graph,
        )
    return PlatformStats(
        total_active_jobs=stats.total_active_jobs or 0,
        total_companies=stats.total_companies or 0,
        total_cities=stats.total_cities or 0,
        jobs_added_last_24h=stats.jobs_added_last_24h or 0,
        jobs_closed_last_24h=stats.jobs_closed_last_24h or 0,
        last_full_poll_at=(
            stats.last_full_poll_at.isoformat() if stats.last_full_poll_at else None
        ),
        avg_poll_duration_ms=stats.avg_poll_duration_ms,
        top_companies=top_companies,
        top_roles=top_roles,
        data_freshness=_data_freshness(db),
        graph=graph,
    )
