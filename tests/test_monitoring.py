"""create_watch monitoring config tests."""
from __future__ import annotations

from src.mcp import tools as tool_impl
from src.schemas.matching import MatchResult


def test_create_watch_returns_config(monkeypatch):
    monkeypatch.setattr(
        "src.services.matching.matcher.match_jobs",
        lambda *a, **k: MatchResult(total_matches=12, showing=0),
    )
    out = tool_impl.tool_create_watch(
        skills="Python,Flask",
        target_role="Backend Engineer",
        companies="Stripe,Anthropic",
        location="NYC",
        salary_min=150000,
    )
    assert out["watch_config"]["skills"] == ["Python", "Flask"]
    assert out["watch_config"]["companies"] == ["Stripe", "Anthropic"]
    assert out["current_snapshot"]["matching_jobs_now"] == 12
    assert "as_of" in out["current_snapshot"]
    assert "posted_within_hours=4" in out["instructions_for_client"]


def test_create_watch_empty_defaults(monkeypatch):
    from src.schemas.jobs import JobSearchResult

    monkeypatch.setattr(
        "src.services.job_service.search_jobs",
        lambda *a, **k: JobSearchResult(
            total_results=5, showing=0, offset=0, jobs=[], filters_applied={}, data_freshness="x"
        ),
    )
    out = tool_impl.tool_create_watch()
    assert out["watch_config"]["skills"] == []
    assert out["watch_config"]["remote_ok"] is True
    assert out["current_snapshot"]["matching_jobs_now"] == 5
