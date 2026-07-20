"""HireLoop MCP server — streamable HTTP at /mcp."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from src.mcp import tools as tool_impl

mcp = FastMCP(
    name="hireloop",
    instructions=(
        "Live US job data from 400+ company career pages via localhost MCP. "
        "Search, browse companies, and use graph insights. "
        "Matching tools: match_jobs (ranked fit from your skills), analyze_skills, "
        "get_skill_gaps, and create_watch for client-side monitoring. "
        "Every job is verified on the company's career page. Zero ghost jobs."
    ),
    website_url="http://localhost:8000",
    streamable_http_path="/",
    stateless_http=True,
    json_response=True,
)


@mcp.tool()
def search_jobs(
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
    """Search across 400+ US company career pages. Filter by role, location, company,
    remote policy, experience, salary, seniority, skills, visa sponsorship, and recency.
    Skill and role searches expand via the knowledge graph (e.g. Python includes Flask jobs;
    Backend Engineer includes similar roles). Results include match_type and role_insights
    when available. Pass my_skills (comma-separated) to add a quick_match percentage vs
    each job's skills_required. Every result is a live job verified within the last 2 hours.
    Pass skills as a comma-separated string (e.g. "Python,AWS")."""
    return tool_impl.tool_search_jobs(
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
        skills=skills,
        my_skills=my_skills,
        posted_within_hours=posted_within_hours,
        sort=sort,
        limit=limit,
        offset=offset,
    )


@mcp.tool()
def get_job_details(job_id: str) -> dict:
    """Get full details for a single job listing including the complete job description,
    salary breakdown, all required and nice-to-have skills, visa information, a direct
    apply link, and market_context (role demand, salary percentile, skill rarity when
    the graph is up, company hiring pace)."""
    return tool_impl.tool_get_job_details(job_id)


@mcp.tool()
def list_companies(
    sort: str = "job_count", limit: int = 50, offset: int = 0
) -> dict:
    """List all companies being monitored by HireLoop with their active job counts.
    See which companies are hiring the most right now.
    sort: name | job_count | newest_job"""
    return tool_impl.tool_list_companies(sort=sort, limit=limit, offset=offset)


@mcp.tool()
def get_company_jobs(
    company: str,
    department: str | None = None,
    seniority: str | None = None,
    sort: str = "newest",
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Get all active jobs from a specific company. See everything they're hiring for right now."""
    return tool_impl.tool_get_company_jobs(
        company=company,
        department=department,
        seniority=seniority,
        sort=sort,
        limit=limit,
        offset=offset,
    )


@mcp.tool()
def get_stats() -> dict:
    """Get overall HireLoop platform statistics: total active jobs, companies monitored,
    top hiring companies, most common roles, and data freshness info."""
    return tool_impl.tool_get_stats()


@mcp.tool()
def get_new_jobs(
    since_hours: int = 24,
    query: str | None = None,
    location: str | None = None,
    company: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """Get jobs that were newly posted since a specific time. Great for checking
    'what's new since yesterday' or 'what was posted in the last hour.'"""
    return tool_impl.tool_get_new_jobs(
        since_hours=since_hours,
        query=query,
        location=location,
        company=company,
        limit=limit,
        offset=offset,
    )


@mcp.tool()
def get_role_insights(role: str) -> dict:
    """Get market intelligence for a specific job role. See which skills are most in
    demand, what the typical salary range is, which companies hire for this role, where
    the jobs are concentrated, and what similar roles exist. All data learned from live
    job postings, refreshed every 2 hours."""
    return tool_impl.tool_get_role_insights(role)


@mcp.tool()
def get_skill_insights(skill: str) -> dict:
    """Get market intelligence for a specific skill. See which roles require it, what it
    pays, which companies use it, and what related skills are. All data from live job
    postings."""
    return tool_impl.tool_get_skill_insights(skill)


@mcp.tool()
def get_company_stack(company: str) -> dict:
    """See what technologies a specific company uses based on their current job postings.
    Shows their primary tech stack, what roles they're hiring for, and how their hiring
    compares to similar companies."""
    return tool_impl.tool_get_company_stack(company)


@mcp.tool()
def match_jobs(
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
    """Match your skills and preferences against live jobs. Skills expand through the
    knowledge graph (e.g. TensorFlow implies Python / Deep Learning). Returns ranked
    matches with fit scores, skill overlap, and gap insights.
    Pass skills and companies as comma-separated strings. detail: summary|full|scores_only.
    Use offset with limit to page through all total_matches."""
    return tool_impl.tool_match_jobs(
        skills=skills,
        target_role=target_role,
        location=location,
        remote_ok=remote_ok,
        experience_years=experience_years,
        salary_min=salary_min,
        visa_needed=visa_needed,
        seniority=seniority,
        companies=companies,
        posted_within_hours=posted_within_hours,
        limit=limit,
        offset=offset,
        detail=detail,
    )


@mcp.tool()
def analyze_skills(skills: str) -> dict:
    """See which roles fit your skill set best, with match percentages and missing core
    skills. Pass skills as a comma-separated string from your resume."""
    return tool_impl.tool_analyze_skills(skills)


@mcp.tool()
def get_skill_gaps(skills: str, target_role: str) -> dict:
    """Gap analysis for a target role: skills you have, skills you're close to, and
    skills you need — plus quick wins and salary impact where available."""
    return tool_impl.tool_get_skill_gaps(skills=skills, target_role=target_role)


@mcp.tool()
def create_watch(
    skills: str | None = None,
    target_role: str | None = None,
    companies: str | None = None,
    location: str | None = None,
    remote_ok: bool = True,
    salary_min: int | None = None,
) -> dict:
    """Create a watch configuration the AI client can store and re-use with match_jobs
    or search_jobs (add posted_within_hours=4 to check for new postings). No server-side
    persistence — the client owns the watch state."""
    return tool_impl.tool_create_watch(
        skills=skills,
        target_role=target_role,
        companies=companies,
        location=location,
        remote_ok=remote_ok,
        salary_min=salary_min,
    )


def create_mcp_app():
    """Return the Starlette Streamable HTTP app (mount at /mcp)."""
    return mcp.streamable_http_app()
