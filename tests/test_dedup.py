import uuid

from src.models import Job
from src.services.dedup import check_duplicate


def _job(
    *,
    company: str = "Acme",
    title: str = "Backend Engineer",
    city: str | None = "San Francisco",
    ats: str = "greenhouse",
    remote: str = "onsite",
    status: str = "active",
    job_id: str | None = None,
) -> Job:
    return Job(
        id=uuid.uuid4(),
        source_company_slug=f"{company.lower()}-{ats}-{job_id or uuid.uuid4().hex[:8]}",
        source_ats=ats,
        source_job_id=job_id or uuid.uuid4().hex[:12],
        title_raw=title,
        company_name=company,
        location_city=city,
        remote_policy=remote,
        status=status,
    )


def test_same_company_title_city_is_duplicate(db_session):
    existing = _job(ats="lever")
    new = _job(ats="ashby")
    db_session.add(existing)
    db_session.add(new)
    db_session.flush()

    keeper = check_duplicate(new, db_session)
    assert keeper is existing
    assert existing.status == "active"
    assert new.status == "duplicate"


def test_similar_title_detected(db_session):
    existing = _job(title="Senior Backend Engineer", ats="lever")
    new = _job(title="Sr Backend Engineer", ats="ashby")
    db_session.add_all([existing, new])
    db_session.flush()

    assert check_duplicate(new, db_session) is existing
    assert new.status == "duplicate"


def test_different_city_not_duplicate(db_session):
    existing = _job(city="San Francisco")
    new = _job(city="New York City", ats="ashby")
    db_session.add_all([existing, new])
    db_session.flush()

    assert check_duplicate(new, db_session) is None
    assert new.status == "active"


def test_different_company_not_duplicate(db_session):
    existing = _job(company="Acme")
    new = _job(company="OtherCo", ats="ashby")
    db_session.add_all([existing, new])
    db_session.flush()

    assert check_duplicate(new, db_session) is None


def test_very_different_title_not_duplicate(db_session):
    existing = _job(title="Backend Engineer")
    new = _job(title="Chief Financial Officer", ats="ashby")
    db_session.add_all([existing, new])
    db_session.flush()

    assert check_duplicate(new, db_session) is None


def test_both_remote_is_duplicate(db_session):
    existing = _job(city=None, remote="remote", ats="lever")
    new = _job(city=None, remote="remote", ats="ashby")
    db_session.add_all([existing, new])
    db_session.flush()

    assert check_duplicate(new, db_session) is existing
    assert new.status == "duplicate"


def test_preferred_source_wins_new_better(db_session):
    existing = _job(ats="greenhouse")
    new = _job(ats="custom")
    db_session.add_all([existing, new])
    db_session.flush()

    keeper = check_duplicate(new, db_session)
    assert keeper is new
    assert new.status == "active"
    assert existing.status == "duplicate"


def test_preferred_source_wins_existing_better(db_session):
    existing = _job(ats="custom")
    new = _job(ats="greenhouse")
    db_session.add_all([existing, new])
    db_session.flush()

    keeper = check_duplicate(new, db_session)
    assert keeper is existing
    assert existing.status == "active"
    assert new.status == "duplicate"


def test_equal_rank_keeps_existing(db_session):
    existing = _job(ats="greenhouse", job_id="old")
    new = _job(ats="greenhouse", job_id="new")
    db_session.add_all([existing, new])
    db_session.flush()

    keeper = check_duplicate(new, db_session)
    assert keeper is existing
    assert existing.status == "active"
    assert new.status == "duplicate"
