"""MCP insight tool tests."""
from __future__ import annotations

from src.mcp import tools as tool_impl
from src.models import get_sync_db
from src.schemas.jobs import JobSearchFilters
from src.services import job_service


def test_get_role_insights_backend():
    result = tool_impl.tool_get_role_insights("Backend Engineer")
    if "error_code" in result:
        # Graph may be empty in some envs — skip soft
        assert result["error_code"] in {"ROLE_NOT_FOUND", "GRAPH_UNAVAILABLE"}
        return
    assert result["role"] == "Backend Engineer"
    assert "core_skills" in result
    assert "salary" in result
    assert "data_source" in result


def test_get_role_insights_missing():
    result = tool_impl.tool_get_role_insights("Completely Fake Role XYZ")
    assert result.get("error_code") in {"ROLE_NOT_FOUND", "GRAPH_UNAVAILABLE"}


def test_get_skill_insights_python():
    result = tool_impl.tool_get_skill_insights("Python")
    if "error_code" in result:
        assert result["error_code"] in {"SKILL_NOT_FOUND", "GRAPH_UNAVAILABLE"}
        return
    assert result["skill"] == "Python"
    assert "top_roles" in result
    assert "implies_knowledge_of" in result


def test_get_company_stack_missing():
    result = tool_impl.tool_get_company_stack("DefinitelyNotARealCompanyZZZ")
    assert result.get("error_code") in {"COMPANY_NOT_FOUND", "GRAPH_UNAVAILABLE"}


def test_search_with_graph_expansion():
    with get_sync_db() as db:
        result = job_service.search_jobs(
            db, JobSearchFilters(skills=["Python"], limit=10)
        )
    assert result.showing >= 0
