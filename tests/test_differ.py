from src.models import Job, JobSourceConfig
from src.services.differ import apply_diff, diff_jobs
from src.services.field_mapper import MappedJob

SLUG = "test-differ-co"
ATS = "greenhouse"


def mapped(job_id: str, title: str = "Engineer", description: str = "desc") -> MappedJob:
    return MappedJob(id=job_id, title=title, description=description)


def db_job(job_id: str, title: str = "Engineer", description: str = "desc") -> Job:
    return Job(
        source_company_slug=SLUG,
        source_ats=ATS,
        source_job_id=job_id,
        title_raw=title,
        company_name="Test Differ Co",
        description_html=description,
        status="active",
        consecutive_misses=0,
    )


def make_config(db_session) -> JobSourceConfig:
    config = JobSourceConfig(
        company_name="Test Differ Co",
        company_slug=SLUG,
        ats_type=ATS,
        api_endpoint="https://example.com/jobs",
        field_mapping={"id": "id", "title": "title"},
    )
    db_session.add(config)
    db_session.flush()
    return config


# --- diff_jobs ---


def test_all_new():
    result = diff_jobs(SLUG, ATS, [mapped("1"), mapped("2"), mapped("3")], [])
    assert len(result.new_jobs) == 3
    assert result.updated_jobs == []
    assert result.missing_job_ids == []


def test_all_unchanged():
    api = [mapped("1"), mapped("2"), mapped("3")]
    db = [db_job("1"), db_job("2"), db_job("3")]
    result = diff_jobs(SLUG, ATS, api, db)
    assert result.new_jobs == []
    assert result.updated_jobs == []
    assert result.missing_job_ids == []
    assert result.unchanged_count == 3


def test_mixed_new_and_missing():
    api = [mapped("1"), mapped("2"), mapped("3")]
    db = [db_job("1"), db_job("2"), db_job("9")]
    result = diff_jobs(SLUG, ATS, api, db)
    assert [j.id for j in result.new_jobs] == ["3"]
    assert result.updated_jobs == []
    assert result.missing_job_ids == ["9"]


def test_changed_title_detected_as_updated():
    result = diff_jobs(SLUG, ATS, [mapped("1", title="Senior Engineer")], [db_job("1")])
    assert len(result.updated_jobs) == 1


def test_changed_description_detected_as_updated():
    result = diff_jobs(SLUG, ATS, [mapped("1", description="brand new text")], [db_job("1")])
    assert len(result.updated_jobs) == 1


def test_same_title_and_description_unchanged():
    result = diff_jobs(SLUG, ATS, [mapped("1")], [db_job("1")])
    assert result.updated_jobs == []
    assert result.unchanged_count == 1


def test_formatting_only_change_is_unchanged():
    api = [mapped("1", description="<p>Hello&nbsp;&amp; World</p>")]
    db = [db_job("1", description="hello  & world")]
    result = diff_jobs(SLUG, ATS, api, db)
    assert result.updated_jobs == []
    assert result.unchanged_count == 1


def test_empty_api_all_missing():
    db = [db_job(str(i)) for i in range(5)]
    result = diff_jobs(SLUG, ATS, [], db)
    assert result.new_jobs == []
    assert result.updated_jobs == []
    assert sorted(result.missing_job_ids) == sorted(str(i) for i in range(5))


def test_empty_api_empty_db():
    result = diff_jobs(SLUG, ATS, [], [])
    assert result.new_jobs == []
    assert result.missing_job_ids == []
    assert result.unchanged_count == 0


# --- apply_diff (grace period) ---


def poll(db_session, config, api_jobs):
    db_jobs = list(
        db_session.query(Job).filter(Job.source_company_slug == config.company_slug).all()
    )
    diff = diff_jobs(config.company_slug, config.ats_type, api_jobs, db_jobs)
    result = apply_diff(diff, config, db_session)
    db_session.flush()
    return result


def get_job(db_session, job_id):
    return (
        db_session.query(Job)
        .filter(Job.source_company_slug == SLUG, Job.source_job_id == job_id)
        .one()
    )


def test_missing_once_stays_active(db_session):
    config = make_config(db_session)
    poll(db_session, config, [mapped("1")])
    result = poll(db_session, config, [])
    job = get_job(db_session, "1")
    assert job.consecutive_misses == 1
    assert job.status == "active"
    assert result.jobs_missing_grace == 1
    assert result.jobs_closed == 0


def test_missing_twice_closes(db_session):
    config = make_config(db_session)
    poll(db_session, config, [mapped("1")])
    poll(db_session, config, [])
    result = poll(db_session, config, [])
    job = get_job(db_session, "1")
    assert job.consecutive_misses == 2
    assert job.status == "closed"
    assert job.closed_at is not None
    assert result.jobs_closed == 1


def test_miss_then_reappear_resets(db_session):
    config = make_config(db_session)
    poll(db_session, config, [mapped("1")])
    poll(db_session, config, [])
    poll(db_session, config, [mapped("1")])
    job = get_job(db_session, "1")
    assert job.consecutive_misses == 0
    assert job.status == "active"


def test_closed_job_reappears_reopens(db_session):
    config = make_config(db_session)
    poll(db_session, config, [mapped("1")])
    poll(db_session, config, [])
    poll(db_session, config, [])
    assert get_job(db_session, "1").status == "closed"
    poll(db_session, config, [mapped("1")])
    job = get_job(db_session, "1")
    assert job.status == "active"
    assert job.closed_at is None
    assert job.consecutive_misses == 0


def test_long_location_is_clipped_not_crashed(db_session):
    config = make_config(db_session)
    long_city = "Campus A; Campus B; Campus C - " + "x" * 200
    api = [MappedJob(id="1", title="Teacher", location=f"{long_city}, TX")]
    poll(db_session, config, api)
    job = get_job(db_session, "1")
    assert len(job.location_city) <= 100


def test_same_job_id_across_companies_no_collision(db_session):
    """Two custom tenants reusing the same source_job_id must both insert."""
    config_a = make_config(db_session)
    config_b = JobSourceConfig(
        company_name="Other Co",
        company_slug="other-co",
        ats_type=ATS,
        api_endpoint="https://example.com/jobs",
        field_mapping={"id": "id", "title": "title"},
    )
    db_session.add(config_b)
    db_session.flush()

    poll(db_session, config_a, [mapped("31726", title="Job at A")])
    poll(db_session, config_b, [mapped("31726", title="Job at B")])

    a = (
        db_session.query(Job)
        .filter(Job.source_company_slug == "test-differ-co", Job.source_job_id == "31726")
        .one()
    )
    b = (
        db_session.query(Job)
        .filter(Job.source_company_slug == "other-co", Job.source_job_id == "31726")
        .one()
    )
    assert a.title_raw == "Job at A"
    assert b.title_raw == "Job at B"


def test_new_job_inserted_with_parsed_fields(db_session):
    config = make_config(db_session)
    api = [
        MappedJob(
            id="42",
            title="Backend Engineer",
            location="Austin, TX",
            description="<p>$150,000 - $200,000. 5+ years of experience. Fully remote.</p>",
        )
    ]
    result = poll(db_session, config, api)
    assert result.jobs_inserted == 1
    job = get_job(db_session, "42")
    assert job.salary_min == 150000
    assert job.salary_max == 200000
    assert job.experience_min == 5
    assert job.location_city == "Austin"
    assert job.location_state == "TX"
    assert job.remote_policy == "remote"
    assert "<p>" in job.description_html
    assert "<p>" not in job.description_text
