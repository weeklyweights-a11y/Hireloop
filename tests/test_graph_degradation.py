"""Graceful degradation when Neo4j is down or stale."""
from __future__ import annotations

from src.graph import insights as gi
from src.mcp import tools as tool_impl
from src.models import get_sync_db
from src.schemas.jobs import JobSearchFilters
from src.services import job_service


def test_search_works_when_neo4j_down(monkeypatch):
    monkeypatch.setattr("src.graph.queries.is_available", lambda: False)
    monkeypatch.setattr("src.services.job_service.expand_skills", lambda s: [s])
    monkeypatch.setattr("src.services.job_service.expand_roles", lambda *a, **k: [])
    monkeypatch.setattr(
        "src.services.job_service.role_insights_for_title", lambda *a, **k: None
    )
    with get_sync_db() as db:
        result = job_service.search_jobs(
            db, JobSearchFilters(query="software", limit=5)
        )
    assert isinstance(result.total_results, int)


def test_insight_tools_error_when_neo4j_down(monkeypatch):
    monkeypatch.setattr("src.graph.insights.is_available", lambda: False)
    result = tool_impl.tool_get_role_insights("Backend Engineer")
    assert result["error_code"] == "GRAPH_UNAVAILABLE"
    assert "Job search still works" in result["error"]


def test_stale_warning(monkeypatch):
    monkeypatch.setattr("src.graph.insights.graph_age_hours", lambda: 8.0)
    assert gi._stale_warning() is not None
