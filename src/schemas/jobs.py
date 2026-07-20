from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


def format_ago(dt: datetime | None) -> str:
    if dt is None:
        return "unknown"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    seconds = int((datetime.now(timezone.utc) - dt).total_seconds())
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        mins = seconds // 60
        return f"{mins} minute{'s' if mins != 1 else ''} ago"
    if seconds < 86400:
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = seconds // 86400
    return f"{days} day{'s' if days != 1 else ''} ago"


class JobSearchFilters(BaseModel):
    query: str | None = None
    location: str | None = None
    country: str | None = None
    company: str | None = None
    remote: str | None = None  # any | remote | hybrid | onsite
    experience_max: int | None = None
    salary_min: int | None = None
    seniority: str | None = None
    visa_sponsorship: bool | None = None
    employment_type: str | None = None
    skills: list[str] | None = None
    my_skills: list[str] | None = None  # optional quick_match vs skills_required
    posted_within_hours: int | None = None
    sort: str = "newest"  # newest | salary_high | salary_low | relevance
    limit: int = 20
    offset: int = 0


class JobSummary(BaseModel):
    id: str
    title: str
    title_normalized: str | None = None
    company: str
    location: str | None = None
    location_city: str | None = None
    location_state: str | None = None
    location_country: str | None = None
    location_metro: str | None = None
    remote_policy: str | None = None
    seniority: str | None = None
    employment_type: str | None = None
    salary_range: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    experience: str | None = None
    experience_min: int | None = None
    experience_max: int | None = None
    skills_required: list[str] = Field(default_factory=list)
    skills_nice_to_have: list[str] = Field(default_factory=list)
    skills_implied: list[str] = Field(default_factory=list)
    visa_sponsorship: str | None = None
    department: str | None = None
    apply_url: str | None = None
    first_seen: str | None = None
    last_verified: str | None = None
    freshness: str = "unknown"
    relevance_score: int | None = None
    match_type: str | None = None
    role_insights: dict | None = None
    quick_match: int | None = None  # 0-100 vs skills_required when my_skills set


class JobSearchResult(BaseModel):
    total_results: int
    showing: int
    offset: int
    jobs: list[JobSummary]
    filters_applied: dict
    data_freshness: str


class JobDetail(JobSummary):
    description_text: str | None = None
    description_html: str | None = None
    source_ats: str | None = None
    source_company_slug: str | None = None
    source_url: str | None = None
    status: str | None = None
    market_context: dict | None = None


class CompanySummary(BaseModel):
    company_name: str
    active_jobs: int
    newest_job_at: str | None = None


class CompanyJobsResult(BaseModel):
    company_name: str
    active_jobs: int
    jobs: list[JobSummary]


class PlatformStats(BaseModel):
    total_active_jobs: int = 0
    total_companies: int = 0
    total_cities: int = 0
    jobs_added_last_24h: int = 0
    jobs_closed_last_24h: int = 0
    last_full_poll_at: str | None = None
    avg_poll_duration_ms: int | None = None
    top_companies: list[CompanySummary] = Field(default_factory=list)
    top_roles: list[dict] = Field(default_factory=list)
    data_freshness: str = "unknown"
    graph: dict | None = None
