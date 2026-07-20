"""MCP matching tool smoke tests (mocked matcher where heavy)."""
from __future__ import annotations

from src.mcp import tools as tool_impl
from src.schemas.jobs import JobSummary
from src.schemas.matching import JobMatch, MatchResult, MatchScore


def test_match_jobs_requires_skills():
    out = tool_impl.tool_match_jobs(skills="")
    assert out["error_code"] == "INVALID_REQUEST"


def test_match_jobs_maps_your_profile(monkeypatch):
    result = MatchResult(
        total_matches=1,
        showing=1,
        matches=[
            JobMatch(
                job=JobSummary(
                    id="00000000-0000-0000-0000-000000000099",
                    title="Backend Engineer",
                    company="Acme",
                ),
                score=MatchScore(
                    overall=80,
                    skills_fit=90,
                    role_fit=50,
                    preference_fit=80,
                    freshness=100,
                ),
            )
        ],
        profile_summary={"direct_skills": ["Python"], "total_skills_used": 1},
        data_freshness="just now",
    )

    monkeypatch.setattr(
        "src.services.matching.matcher.match_jobs",
        lambda *a, **k: result,
    )
    out = tool_impl.tool_match_jobs(skills="Python")
    assert "your_profile" in out
    assert out["showing"] == 1
    assert out["matches"][0]["score"]["overall"] == 80


def test_get_skill_gaps_requires_role():
    out = tool_impl.tool_get_skill_gaps(skills="Python", target_role="")
    assert out["error_code"] == "INVALID_REQUEST"


def test_website_url_localhost():
    import src.mcp.server as srv

    src = open(srv.__file__, encoding="utf-8").read()
    assert 'website_url="http://localhost:8000"' in src
    assert "hireloop.dev" not in src


def test_detail_scores_only():
    from src.services.matching.response_tiers import apply_detail_tier

    payload = {
        "matches": [
            {
                "job": {
                    "id": "1",
                    "title": "BE",
                    "company": "Acme",
                    "location": "NYC",
                    "salary_range": "$1",
                },
                "score": {"overall": 88, "skills_fit": 90},
                "skills_analysis": {"matched": ["Python"], "missing": ["Go"]},
            }
        ],
        "skill_gaps": [{"skill": "Go"}],
    }
    out = apply_detail_tier(payload, "scores_only")
    assert "location" not in out["matches"][0]["job"]
    assert out["matches"][0]["score"] == {"overall": 88}
    assert "skill_gaps" not in out


def test_detail_summary_caps_lists():
    from src.services.matching.response_tiers import apply_detail_tier

    matched = [{"skill": f"S{i}"} for i in range(10)]
    payload = {
        "matches": [
            {
                "job": {"id": "1", "title": "T", "company": "C"},
                "score": {"overall": 70},
                "skills_analysis": {"matched": matched, "missing": list("abcdef")},
            }
        ],
        "skill_gaps": [{"skill": str(i)} for i in range(20)],
    }
    out = apply_detail_tier(payload, "summary")
    assert len(out["matches"][0]["skills_analysis"]["matched"]) == 3
    assert len(out["matches"][0]["skills_analysis"]["missing"]) == 2
    assert len(out["skill_gaps"]) == 5
