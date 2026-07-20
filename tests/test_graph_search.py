"""Graph-enhanced search tests."""
from __future__ import annotations

import time
import uuid

from sqlalchemy import text

from src.models import Job, get_sync_db
from src.schemas.jobs import JobSearchFilters
from src.services import job_service


def _job(**kwargs) -> Job:
    jid = uuid.uuid4()
    defaults = dict(
        id=jid,
        source_company_slug=kwargs.pop("slug", f"gsr-{jid.hex[:8]}"),
        source_ats="test",
        source_job_id=f"id-{jid.hex[:12]}",
        title_raw=kwargs.get("title_normalized") or "Engineer",
        company_name="SearchTestCo",
        skills_required=[],
        skills_nice_to_have=[],
        skills_implied=[],
        status="active",
    )
    defaults.update(kwargs)
    return Job(**defaults)


def test_expand_skills_no_dupes():
    from src.graph.queries import expand_skills

    expanded = expand_skills("Python")
    assert expanded[0] == "Python"
    assert len(expanded) == len(set(expanded))


def test_search_python_includes_flask_via_implied():
    marker = uuid.uuid4().hex[:8]
    slug = f"flask-{marker}"
    with get_sync_db() as db:
        db.add(
            _job(
                slug=slug,
                title_normalized="Backend Engineer",
                title_raw="Backend Engineer",
                company_name=f"FlaskOnlyCo-{marker}",
                skills_required=["Flask"],
                skills_implied=["Python"],
            )
        )

    with get_sync_db() as db:
        result = job_service.search_jobs(
            db,
            JobSearchFilters(
                skills=["Python"],
                company=f"FlaskOnlyCo-{marker}",
                limit=10,
            ),
        )
    assert result.total_results >= 1
    hit = result.jobs[0]
    assert hit.match_type == "implied_skill"
    assert "Python" in (hit.skills_implied or [])

    with get_sync_db() as db:
        db.execute(
            text("DELETE FROM jobs WHERE source_company_slug = :s"),
            {"s": slug},
        )


def test_search_fallback_when_neo4j_mocked_down(monkeypatch):
    monkeypatch.setattr("src.graph.queries.is_available", lambda: False)
    monkeypatch.setattr("src.services.job_service.expand_skills", lambda s: [s])
    monkeypatch.setattr("src.services.job_service.expand_roles", lambda *a, **k: [])
    monkeypatch.setattr(
        "src.services.job_service.role_insights_for_title", lambda *a, **k: None
    )
    with get_sync_db() as db:
        result = job_service.search_jobs(
            db, JobSearchFilters(query="engineer", limit=5)
        )
    assert result.showing >= 0


def test_role_expansion_threshold():
    from src.graph.queries import expand_roles

    similar = expand_roles("Backend Engineer", min_overlap=0.6)
    assert "Backend Engineer" not in similar
    assert len(similar) == len(set(similar))


def test_direct_ranks_above_implied():
    """Spec 4.5 ranking matrix: direct title+skill > direct+implied > similar+direct > similar+implied."""
    from src.services.job_service import _combo_rank

    role = "Backend Engineer"
    similar = {"Platform Engineer"}
    skills = ["Python"]

    def job(title: str, required: list[str], implied: list[str] | None = None) -> Job:
        return _job(
            title_normalized=title,
            title_raw=title,
            skills_required=required,
            skills_implied=implied or [],
        )

    direct_direct = _combo_rank(
        job(role, ["Python"]),
        canonical_role=role,
        similar_roles=similar,
        requested_skills=skills,
        base_score=0,
    )
    direct_implied = _combo_rank(
        job(role, ["Flask"], ["Python"]),
        canonical_role=role,
        similar_roles=similar,
        requested_skills=skills,
        base_score=0,
    )
    similar_direct = _combo_rank(
        job("Platform Engineer", ["Python"]),
        canonical_role=role,
        similar_roles=similar,
        requested_skills=skills,
        base_score=0,
    )
    similar_implied = _combo_rank(
        job("Platform Engineer", ["Flask"], ["Python"]),
        canonical_role=role,
        similar_roles=similar,
        requested_skills=skills,
        base_score=0,
    )

    assert direct_direct > direct_implied > similar_direct > similar_implied


def test_search_smoke_under_300ms():
    filters = JobSearchFilters(
        skills=["Python"], query="Backend Engineer", limit=10
    )
    with get_sync_db() as db:
        # Warm Neo4j + connection pool (spec 4.7 is warm)
        job_service.search_jobs(db, filters)
        t0 = time.perf_counter()
        job_service.search_jobs(db, filters)
        elapsed_ms = (time.perf_counter() - t0) * 1000
    assert elapsed_ms < 300, f"search took {elapsed_ms:.0f}ms"
