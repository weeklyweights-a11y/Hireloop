"""Matcher threshold / gap aggregation tests (no live Neo4j)."""
from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.schemas.matching import (
    ExpandedSkillProfile,
    JobMatch,
    MatchFilters,
    MatchScore,
    SkillWithConfidence,
)
from src.schemas.jobs import JobSummary
from src.services.matching import matcher as matcher_mod


def _summary(**kw):
    base = dict(
        id="00000000-0000-0000-0000-000000000001",
        title="Backend Engineer",
        title_normalized="Backend Engineer",
        company="Acme",
        skills_required=["Python"],
    )
    base.update(kw)
    return JobSummary(**base)


def test_aggregate_gaps_frequency():
    profile = ExpandedSkillProfile(
        direct=[SkillWithConfidence(name="Python", confidence=1.0, source="direct")],
        all_skills=[SkillWithConfidence(name="Python", confidence=1.0, source="direct")],
    )
    matches = [
        JobMatch(
            job=_summary(),
            score=MatchScore(
                overall=80,
                skills_fit=80,
                role_fit=50,
                preference_fit=100,
                freshness=100,
                missing_skills=["Docker", "Kubernetes"],
            ),
        ),
        JobMatch(
            job=_summary(title="Platform Engineer", title_normalized="Platform Engineer"),
            score=MatchScore(
                overall=70,
                skills_fit=70,
                role_fit=50,
                preference_fit=100,
                freshness=100,
                missing_skills=["Docker"],
            ),
        ),
    ]
    gaps = matcher_mod._aggregate_gaps(matches, profile)
    by_name = {g.skill: g for g in gaps}
    assert by_name["Docker"].frequency == 1.0
    assert abs(by_name["Kubernetes"].frequency - 0.5) < 1e-9


def test_match_jobs_drops_below_threshold(monkeypatch):
    profile = ExpandedSkillProfile(
        direct=[SkillWithConfidence(name="Python", confidence=1.0, source="direct")],
        all_skills=[SkillWithConfidence(name="Python", confidence=1.0, source="direct")],
    )
    job = SimpleNamespace(
        id="1",
        title_raw="X",
        title_normalized="X",
        company_name="C",
        skills_required=["Z"],
        skills_nice_to_have=[],
        location_city=None,
        location_metro=None,
        location_state=None,
        location_country="US",
        remote_policy="unknown",
        seniority=None,
        employment_type="full_time",
        salary_min=None,
        salary_max=None,
        experience_min=None,
        experience_max=None,
        visa_sponsorship="unknown",
        department=None,
        apply_url=None,
        first_seen_at=datetime.now(UTC),
        last_verified_at=datetime.now(UTC),
        skills_implied=[],
    )

    monkeypatch.setattr(matcher_mod, "expand_user_skills", lambda s: profile)
    monkeypatch.setattr(matcher_mod, "expand_roles", lambda *a, **k: [])
    monkeypatch.setattr(
        matcher_mod,
        "DataLoader",
        SimpleNamespace(get=lambda: SimpleNamespace(locations={}, title_alias_index={}, taxonomy={})),
    )
    monkeypatch.setattr(
        matcher_mod,
        "_resolve_query_role",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        matcher_mod,
        "score_match",
        lambda *a, **k: MatchScore(
            overall=20,
            skills_fit=20,
            role_fit=50,
            preference_fit=50,
            freshness=50,
        ),
    )

    db = MagicMock()
    db.scalars.return_value.all.return_value = [job]
    result = matcher_mod.match_jobs(db, ["Python"], MatchFilters(limit=10), profile=profile)
    assert result.total_matches == 0
    assert result.showing == 0
