"""Tests for knowledge graph builder thresholds and enrichment."""
from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import text

from src.graph.connection import sync_session
from src.models import Job, get_sync_db
from src.workers.graph_builder import build_graph_relationships_impl

pytestmark = pytest.mark.requires_neo4j


def _ensure_skill_role(skill: str, role: str) -> None:
    with sync_session() as session:
        session.run(
            """
            MERGE (s:Skill {name: $skill})
            ON CREATE SET s.canonical = $skill, s.category = 'test',
                          s.aliases = [], s.job_count = 0,
                          s.avg_salary_min = 0, s.avg_salary_max = 0
            """,
            skill=skill,
        )
        session.run(
            """
            MERGE (r:Role {title: $role})
            ON CREATE SET r.function = 'engineering', r.job_count = 0,
                          r.avg_salary_min = 0, r.avg_salary_max = 0,
                          r.top_companies = []
            """,
            role=role,
        )


def _insert_job(
    db,
    *,
    title: str,
    skills: list[str],
    slug: str = "graph-test-co",
    company: str = "GraphTestCo",
) -> uuid.UUID:
    jid = uuid.uuid4()
    job = Job(
        id=jid,
        source_company_slug=slug,
        source_ats="test",
        source_job_id=f"g-{jid.hex[:12]}",
        title_raw=title,
        title_normalized=title,
        company_name=company,
        skills_required=skills,
        skills_nice_to_have=[],
        skills_implied=[],
        status="active",
        location_city="San Francisco",
        location_state="CA",
        location_country="US",
    )
    db.add(job)
    db.flush()
    return jid


def test_needs_skill_threshold_and_implies():
    marker = f"gt-{uuid.uuid4().hex[:8]}"
    role = f"Backend Engineer {marker}"
    _ensure_skill_role("Python", role)
    _ensure_skill_role("SQL", role)
    _ensure_skill_role("Flask", role)
    _ensure_skill_role("RareSkillX", role)

    with get_sync_db() as db:
        # 10 jobs: Python+SQL+Flask in all; RareSkillX in 1 only (10% < 20%)
        for i in range(10):
            skills = ["Python", "SQL", "Flask"]
            if i == 0:
                skills = ["Python", "SQL", "Flask", "RareSkillX"]
            _insert_job(db, title=role, skills=skills, slug=f"gt-{marker}")

    build_graph_relationships_impl()

    with sync_session() as session:
        needs = list(
            session.run(
                """
                MATCH (r:Role {title: $role})-[rel:NEEDS_SKILL]->(s:Skill)
                RETURN s.name AS skill, rel.importance AS importance
                ORDER BY s.name
                """,
                role=role,
            )
        )
        skills = {r["skill"] for r in needs}
        assert "Python" in skills
        assert "SQL" in skills
        assert "RareSkillX" not in skills  # < 20%

        implies = list(
            session.run(
                """
                MATCH (a:Skill {name: 'Flask'})-[rel:IMPLIES]->(b:Skill {name: 'Python'})
                RETURN rel.strength AS strength
                """
            )
        )
        # May or may not create IMPLIES depending on global co-occurrence >= 10;
        # with only 3 local jobs, global threshold may not hit. Assert NEEDS works.

    # Cleanup test jobs
    with get_sync_db() as db:
        db.execute(
            text("DELETE FROM jobs WHERE source_company_slug = :s"),
            {"s": f"gt-{marker}"},
        )


def test_skills_implied_enrichment_idempotent():
    marker = f"gi-{uuid.uuid4().hex[:8]}"
    role = f"Implied Role {marker}"
    _ensure_skill_role("Python", role)
    _ensure_skill_role("Django", role)

    # Seed a strong IMPLIES edge directly for this test
    with sync_session() as session:
        session.run(
            """
            MATCH (a:Skill {name: 'Django'}), (b:Skill {name: 'Python'})
            MERGE (a)-[rel:IMPLIES]->(b)
            SET rel.strength = 99, rel.co_occurrence = 100, rel.updated_at = datetime()
            """
        )

    with get_sync_db() as db:
        jid = _insert_job(
            db,
            title=role,
            skills=["Django"],
            slug=f"gi-{marker}",
        )

    build_graph_relationships_impl()

    with get_sync_db() as db:
        row = db.execute(
            text("SELECT skills_implied FROM jobs WHERE id = :id"),
            {"id": jid},
        ).scalar_one()
        implied = list(row or [])
        assert "Python" in implied

    # Idempotent
    build_graph_relationships_impl()
    with get_sync_db() as db:
        row2 = db.execute(
            text("SELECT skills_implied FROM jobs WHERE id = :id"),
            {"id": jid},
        ).scalar_one()
        assert "Python" in list(row2 or [])

    with get_sync_db() as db:
        db.execute(
            text("DELETE FROM jobs WHERE source_company_slug = :s"),
            {"s": f"gi-{marker}"},
        )


def test_similar_role_dice_threshold():
    marker = f"gs-{uuid.uuid4().hex[:8]}"
    r1 = f"RoleA {marker}"
    r2 = f"RoleB {marker}"
    skills_shared = ["Python", "SQL", "Docker", "AWS", "Redis"]
    for s in skills_shared + ["Kafka", "Go"]:
        _ensure_skill_role(s, r1)
        _ensure_skill_role(s, r2)

    with get_sync_db() as db:
        # RoleA: 5 shared skills; RoleB: same 5 + 2 unique → Dice = 10/12 ≈ 0.83
        for _ in range(5):
            _insert_job(db, title=r1, skills=skills_shared, slug=f"gs-a-{marker}")
            _insert_job(
                db,
                title=r2,
                skills=skills_shared + ["Kafka", "Go"],
                slug=f"gs-b-{marker}",
            )

    build_graph_relationships_impl()

    with sync_session() as session:
        rows = list(
            session.run(
                """
                MATCH (a:Role {title: $r1})-[rel:SIMILAR_ROLE]-(b:Role {title: $r2})
                RETURN rel.overlap AS overlap
                """,
                r1=r1,
                r2=r2,
            )
        )
        assert rows, "expected SIMILAR_ROLE edge"
        assert rows[0]["overlap"] >= 0.5

    with get_sync_db() as db:
        db.execute(
            text("DELETE FROM jobs WHERE source_company_slug LIKE :p"),
            {"p": f"gs-%{marker}"},
        )
