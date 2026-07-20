"""Seed Neo4j with Skill, Role, Company, Location nodes + constraints.

Run: python -m scripts.seed_graph
"""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select, text

from src.graph.connection import sync_session
from src.models import JobSourceConfig, get_sync_db

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "data"

CONSTRAINTS = [
    "CREATE CONSTRAINT skill_name IF NOT EXISTS FOR (s:Skill) REQUIRE s.name IS UNIQUE",
    "CREATE CONSTRAINT role_title IF NOT EXISTS FOR (r:Role) REQUIRE r.title IS UNIQUE",
    "CREATE CONSTRAINT company_slug IF NOT EXISTS FOR (c:Company) REQUIRE c.slug IS UNIQUE",
    "CREATE CONSTRAINT location_city_state IF NOT EXISTS FOR (l:Location) REQUIRE (l.city, l.state) IS UNIQUE",
    "CREATE CONSTRAINT graph_meta_id IF NOT EXISTS FOR (m:GraphMeta) REQUIRE m.id IS UNIQUE",
]


def seed() -> dict[str, int]:
    skills = json.loads((DATA / "skills.json").read_text(encoding="utf-8"))
    roles = json.loads((DATA / "title_taxonomy.json").read_text(encoding="utf-8"))

    with get_sync_db() as db:
        companies = db.scalars(select(JobSourceConfig)).all()
        loc_rows = db.execute(
            text(
                """
                SELECT DISTINCT location_city, location_state, location_country, location_metro
                FROM jobs
                WHERE location_city IS NOT NULL
                """
            )
        ).all()

    with sync_session() as session:
        for cypher in CONSTRAINTS:
            session.run(cypher)
        session.run("MATCH (n) DETACH DELETE n")

        session.run(
            """
            UNWIND $rows AS row
            CREATE (s:Skill {
                name: row.name,
                canonical: row.canonical,
                category: row.category,
                aliases: row.aliases,
                job_count: 0,
                avg_salary_min: 0,
                avg_salary_max: 0
            })
            """,
            rows=[
                {
                    "name": e["canonical"],
                    "canonical": e["canonical"],
                    "category": e.get("category") or "",
                    "aliases": e.get("aliases") or [],
                }
                for e in skills
            ],
        )

        session.run(
            """
            UNWIND $rows AS row
            CREATE (r:Role {
                title: row.title,
                function: row.function,
                job_count: 0,
                avg_salary_min: 0,
                avg_salary_max: 0,
                top_companies: []
            })
            """,
            rows=[
                {
                    "title": e["canonical"],
                    "function": e.get("function") or "",
                }
                for e in roles
            ],
        )

        session.run(
            """
            UNWIND $rows AS row
            CREATE (c:Company {
                name: row.name,
                slug: row.slug,
                sector: null,
                active_jobs: 0,
                top_roles: [],
                primary_tech: []
            })
            """,
            rows=[
                {"name": c.company_name, "slug": c.company_slug}
                for c in companies
            ],
        )

        session.run(
            """
            UNWIND $rows AS row
            CREATE (l:Location {
                city: row.city,
                state: row.state,
                country: row.country,
                metro: row.metro,
                job_count: 0
            })
            """,
            rows=[
                {
                    "city": r[0],
                    "state": r[1] or "",
                    "country": r[2] or "US",
                    "metro": r[3],
                }
                for r in loc_rows
            ],
        )

        session.run(
            "MERGE (m:GraphMeta {id: 'singleton'}) SET m.last_built_at = null"
        )

        counts = {
            record["label"]: record["n"]
            for record in session.run(
                "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n"
            )
        }

    return counts


def main() -> None:
    counts = seed()
    for label, n in sorted(counts.items()):
        print(f"{label}: {n}")


if __name__ == "__main__":
    main()
