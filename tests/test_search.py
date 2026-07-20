import uuid
from datetime import UTC, datetime, timedelta

from src.models import Job
from src.schemas.jobs import JobSearchFilters
from src.services.job_service import search_jobs

# Isolate from the live 32k-job DB: every fixture job shares this company marker.
MARKER = f"SearchTest-{uuid.uuid4().hex[:8]}"


def _add_job(
    db,
    *,
    title: str,
    company: str | None = None,
    city: str | None = "San Francisco",
    state: str | None = "CA",
    metro: str | None = "San Francisco",
    country: str = "US",
    remote: str = "onsite",
    salary_min: int | None = 120000,
    salary_max: int | None = 180000,
    exp_min: int | None = 3,
    skills: list | None = None,
    visa: str = "unknown",
    title_norm: str | None = None,
    desc: str = "",
    hours_ago: int = 1,
) -> Job:
    co = company or MARKER
    if not co.startswith(MARKER):
        co = f"{MARKER}-{co}"
    job = Job(
        id=uuid.uuid4(),
        source_company_slug=f"{co.lower()}-{uuid.uuid4().hex[:8]}"[:100],
        source_ats="greenhouse",
        source_job_id=uuid.uuid4().hex[:12],
        title_raw=title,
        title_normalized=title_norm or title,
        company_name=co,
        location_city=city,
        location_state=state,
        location_country=country,
        location_metro=metro,
        remote_policy=remote,
        salary_min=salary_min,
        salary_max=salary_max,
        experience_min=exp_min,
        skills_required=skills or [],
        visa_sponsorship=visa,
        description_text=desc,
        description_html=desc,
        status="active",
        first_seen_at=datetime.now(UTC) - timedelta(hours=hours_ago),
        last_verified_at=datetime.now(UTC),
    )
    db.add(job)
    db.flush()
    return job


def _filters(**kwargs) -> JobSearchFilters:
    kwargs.setdefault("company", MARKER)
    return JobSearchFilters(**kwargs)


def test_query_prefers_title_matches(db_session):
    _add_job(
        db_session,
        title="Backend Engineer",
        title_norm="Backend Engineer",
        desc="unrelated",
    )
    _add_job(
        db_session,
        title="Office Manager",
        title_norm="Office Manager",
        desc="We need a backend engineer mindset",
    )
    result = search_jobs(
        db_session, _filters(query="backend engineer", sort="relevance")
    )
    assert result.total_results == 2
    assert result.jobs[0].title_normalized == "Backend Engineer"
    assert (result.jobs[0].relevance_score or 0) > (result.jobs[1].relevance_score or 0)


def test_location_nyc(db_session):
    _add_job(
        db_session,
        title="Eng",
        city="New York City",
        state="NY",
        metro="New York City",
    )
    _add_job(
        db_session,
        title="Eng",
        city="Austin",
        state="TX",
        metro=None,
        company="Austin",
    )
    result = search_jobs(db_session, _filters(location="NYC"))
    assert result.total_results == 1
    assert result.jobs[0].location_city == "New York City"


def test_location_bay_area_metro(db_session):
    _add_job(
        db_session,
        title="Eng",
        city="Mountain View",
        state="CA",
        metro="San Francisco",
    )
    _add_job(
        db_session,
        title="Eng",
        city="Austin",
        state="TX",
        metro=None,
        company="Austin",
    )
    result = search_jobs(db_session, _filters(location="Bay Area"))
    assert result.total_results == 1
    assert result.jobs[0].location_metro == "San Francisco"


def test_company_filter(db_session):
    _add_job(db_session, title="Eng", company="Stripe")
    _add_job(db_session, title="Eng", company="Notion")
    result = search_jobs(db_session, _filters(company=f"{MARKER}-Stripe"))
    assert result.total_results == 1
    assert "Stripe" in result.jobs[0].company


def test_remote_filter(db_session):
    _add_job(db_session, title="Eng", remote="remote", city=None, state=None, metro=None)
    _add_job(db_session, title="Eng", remote="onsite", company="Onsite")
    result = search_jobs(db_session, _filters(remote="remote"))
    assert result.total_results == 1
    assert result.jobs[0].remote_policy == "remote"


def test_salary_min_null_inclusive(db_session):
    _add_job(db_session, title="High", salary_min=200000, salary_max=250000)
    _add_job(
        db_session,
        title="Unknown",
        salary_min=None,
        salary_max=None,
        company="Unknown",
    )
    _add_job(
        db_session,
        title="Low",
        salary_min=80000,
        salary_max=100000,
        company="Low",
    )
    result = search_jobs(db_session, _filters(salary_min=150000))
    titles = {j.title for j in result.jobs}
    assert "High" in titles
    assert "Unknown" in titles
    assert "Low" not in titles


def test_experience_max_null_inclusive(db_session):
    _add_job(db_session, title="Junior", exp_min=1)
    _add_job(db_session, title="Unknown", exp_min=None, company="Unknown")
    _add_job(db_session, title="Senior", exp_min=5, company="Senior")
    result = search_jobs(db_session, _filters(experience_max=3))
    titles = {j.title for j in result.jobs}
    assert "Junior" in titles
    assert "Unknown" in titles
    assert "Senior" not in titles


def test_skills_containment(db_session):
    _add_job(db_session, title="A", skills=["Python", "AWS", "Docker"])
    _add_job(db_session, title="B", skills=["Python"], company="B")
    result = search_jobs(db_session, _filters(skills=["Python", "AWS"]))
    assert result.total_results == 1
    assert result.jobs[0].title == "A"


def test_visa_sponsorship(db_session):
    _add_job(db_session, title="Sponsors", visa="sponsors")
    _add_job(db_session, title="No", visa="no_sponsorship", company="No")
    result = search_jobs(db_session, _filters(visa_sponsorship=True))
    assert result.total_results == 1
    assert result.jobs[0].visa_sponsorship == "sponsors"


def test_no_filters_newest(db_session):
    _add_job(db_session, title="Old", hours_ago=48)
    _add_job(db_session, title="New", hours_ago=1, company="New")
    result = search_jobs(db_session, _filters())
    assert result.total_results == 2
    assert result.jobs[0].title == "New"


def test_pagination(db_session):
    for i in range(5):
        _add_job(db_session, title=f"Job {i}", company=f"Co{i}", hours_ago=i)
    page = search_jobs(db_session, _filters(limit=2, offset=0))
    assert page.showing == 2
    assert page.total_results == 5
    page2 = search_jobs(db_session, _filters(limit=2, offset=2))
    assert page2.showing == 2
    assert {j.id for j in page.jobs}.isdisjoint({j.id for j in page2.jobs})


def test_empty_result(db_session):
    result = search_jobs(db_session, JobSearchFilters(company="NoSuchCompanyXYZ999"))
    assert result.total_results == 0
    assert result.jobs == []


def test_country_filter(db_session):
    _add_job(db_session, title="UK", city="London", state=None, metro=None, country="GB")
    _add_job(
        db_session,
        title="US",
        city="Austin",
        state="TX",
        metro=None,
        country="US",
        company="US",
    )
    result = search_jobs(db_session, _filters(country="GB"))
    assert result.total_results == 1
    assert result.jobs[0].location_country == "GB"


def test_my_skills_adds_quick_match(db_session):
    _add_job(
        db_session,
        title="Full",
        skills=["Python", "AWS", "Docker"],
        title_norm="Backend Engineer",
    )
    _add_job(
        db_session,
        title="Partial",
        skills=["Python", "Go"],
        company="Partial",
        title_norm="Backend Engineer",
    )
    with_skills = search_jobs(
        db_session, _filters(my_skills=["Python", "AWS"])
    )
    assert all(j.quick_match is not None for j in with_skills.jobs)
    by_title = {j.title: j.quick_match for j in with_skills.jobs}
    assert by_title["Full"] == 67  # 2/3
    assert by_title["Partial"] == 50  # 1/2

    without = search_jobs(db_session, _filters())
    assert all(j.quick_match is None for j in without.jobs)


def test_quick_match_empty_required_is_100(db_session):
    _add_job(db_session, title="Open", skills=[], title_norm="Backend Engineer")
    result = search_jobs(db_session, _filters(my_skills=["Python"]))
    assert result.jobs[0].quick_match == 100


def test_job_detail_market_context(db_session):
    from src.services.job_service import get_job_detail

    role = f"EnrichTestRole-{uuid.uuid4().hex[:8]}"
    peer_low = _add_job(
        db_session,
        title="Low",
        title_norm=role,
        salary_min=100000,
        salary_max=120000,
    )
    target = _add_job(
        db_session,
        title="High",
        title_norm=role,
        company="High",
        salary_min=180000,
        salary_max=220000,
        skills=["Python"],
        hours_ago=1,
    )
    detail = get_job_detail(db_session, str(target.id))
    assert detail.market_context is not None
    assert detail.market_context["role_demand"] == 2
    assert detail.market_context["salary_percentile"] == 100
    assert detail.market_context["company_hiring_pace"] >= 1
    assert peer_low.salary_max == 120000
