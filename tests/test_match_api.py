"""POST /jobs/match request body validation (service tested elsewhere)."""

from src.routers.jobs import MatchJobsBody


def test_match_body_defaults():
    body = MatchJobsBody(skills=["Python", "AWS"])
    assert body.detail == "full"
    assert body.remote_ok is True
    assert body.limit == 20
    assert body.offset == 0


def test_match_body_empty_skills_detected():
    body = MatchJobsBody(skills=[])
    assert not [s for s in body.skills if s.strip()]
