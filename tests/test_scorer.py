"""Unit tests for match scorer (mocked role_overlap)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from src.schemas.matching import ExpandedSkillProfile, SkillWithConfidence
from src.services.matching.scorer import score_match


def _job(**kw):
    defaults = dict(
        title_raw="Backend Engineer",
        title_normalized="Backend Engineer",
        company_name="Acme",
        skills_required=["Python", "SQL"],
        skills_nice_to_have=[],
        location_city="New York",
        location_metro="New York",
        location_state="NY",
        remote_policy="hybrid",
        salary_min=100000,
        salary_max=150000,
        experience_min=2,
        visa_sponsorship="unknown",
        first_seen_at=datetime.now(UTC) - timedelta(hours=6),
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _profile(direct: list[str], inferred: list[tuple[str, float]] | None = None):
    d = [
        SkillWithConfidence(name=s, confidence=1.0, source="direct")
        for s in direct
    ]
    inf = [
        SkillWithConfidence(name=n, confidence=c, source="inferred", inferred_from="x")
        for n, c in (inferred or [])
    ]
    return ExpandedSkillProfile(
        direct=d,
        inferred=inf,
        lateral=[],
        all_skills=[*d, *inf],
    )


def test_perfect_skills_near_100(monkeypatch):
    monkeypatch.setattr(
        "src.services.matching.scorer.role_overlap", lambda *a, **k: None
    )
    monkeypatch.setattr(
        "src.services.matching.scorer._resolve_skill_canonical", lambda s, d: s
    )
    score = score_match(
        _profile(["Python", "SQL"]),
        _job(),
        target_role="Backend Engineer",
        locations={},
    )
    assert score.skills_fit >= 95
    assert score.role_fit == 100
    assert score.overall >= 70


def test_empty_required_skills_fit_100(monkeypatch):
    monkeypatch.setattr(
        "src.services.matching.scorer.role_overlap", lambda *a, **k: None
    )
    score = score_match(_profile(["Python"]), _job(skills_required=[]), locations={})
    assert score.skills_fit == 100


def test_no_target_role_neutral_50(monkeypatch):
    monkeypatch.setattr(
        "src.services.matching.scorer.role_overlap", lambda *a, **k: None
    )
    monkeypatch.setattr(
        "src.services.matching.scorer._resolve_skill_canonical", lambda s, d: s
    )
    score = score_match(_profile(["Python", "SQL"]), _job(), locations={})
    assert score.role_fit == 50


def test_inferred_beats_zero(monkeypatch):
    monkeypatch.setattr(
        "src.services.matching.scorer.role_overlap", lambda *a, **k: None
    )
    monkeypatch.setattr(
        "src.services.matching.scorer._resolve_skill_canonical", lambda s, d: s
    )
    score = score_match(
        _profile(["CNN"], inferred=[("Deep Learning", 0.9)]),
        _job(skills_required=["Deep Learning"]),
        locations={},
    )
    assert score.skills_fit >= 80
    assert "Deep Learning" in score.inferred_skills_used


def test_fresh_job_bonus(monkeypatch):
    monkeypatch.setattr(
        "src.services.matching.scorer.role_overlap", lambda *a, **k: None
    )
    monkeypatch.setattr(
        "src.services.matching.scorer._resolve_skill_canonical", lambda s, d: s
    )
    fresh = score_match(
        _profile(["Python", "SQL"]),
        _job(first_seen_at=datetime.now(UTC) - timedelta(hours=1)),
        locations={},
    )
    stale = score_match(
        _profile(["Python", "SQL"]),
        _job(first_seen_at=datetime.now(UTC) - timedelta(days=10)),
        locations={},
    )
    assert fresh.freshness == 100
    assert stale.freshness == 10


def test_salary_mismatch_drops_pref(monkeypatch):
    monkeypatch.setattr(
        "src.services.matching.scorer.role_overlap", lambda *a, **k: None
    )
    monkeypatch.setattr(
        "src.services.matching.scorer._resolve_skill_canonical", lambda s, d: s
    )
    score = score_match(
        _profile(["Python", "SQL"]),
        _job(salary_max=80000),
        salary_min=120000,
        locations={},
    )
    assert score.preference_fit <= 75
