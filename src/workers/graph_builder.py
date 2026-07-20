"""Build Neo4j relationships from Postgres JD data + enrich skills_implied."""
from __future__ import annotations

import time
from collections import defaultdict

import structlog
from sqlalchemy import text

from src.graph.connection import sync_session
from src.models import get_sync_db
from src.workers.celery_app import celery_app

logger = structlog.get_logger()

BATCH = 500

_CLEAR_RELS = """
MATCH ()-[r:NEEDS_SKILL|IMPLIES|SIMILAR_ROLE|USES|HIRES|IN_LOCATION]->()
DELETE r
"""


def _importance(pct: float) -> str:
    if pct >= 70:
        return "core"
    if pct >= 40:
        return "common"
    return "occasional"


def _chunk(rows: list, size: int = BATCH):
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def _build_needs_skill(db) -> dict[str, set[str]]:
    """Return role -> set of skills that passed the 20% threshold (for SIMILAR)."""
    totals = {
        r[0]: int(r[1])
        for r in db.execute(
            text(
                """
                SELECT title_normalized, COUNT(*)
                FROM jobs
                WHERE status = 'active' AND title_normalized IS NOT NULL
                GROUP BY title_normalized
                """
            )
        )
    }
    rows = db.execute(
        text(
            """
            SELECT title_normalized, skill, COUNT(*) AS cnt
            FROM jobs,
                 jsonb_array_elements_text(skills_required) AS skill
            WHERE status = 'active' AND title_normalized IS NOT NULL
            GROUP BY title_normalized, skill
            """
        )
    ).all()

    role_skills: dict[str, set[str]] = defaultdict(set)
    neo_rows = []
    for title, skill, cnt in rows:
        total = totals.get(title) or 0
        if total == 0:
            continue
        pct = cnt * 100.0 / total
        if pct < 20:
            continue
        role_skills[title].add(skill)
        neo_rows.append(
            {
                "role": title,
                "skill": skill,
                "frequency": round(pct, 2),
                "job_count": int(cnt),
                "importance": _importance(pct),
            }
        )

    with sync_session() as session:
        for batch in _chunk(neo_rows):
            session.run(
                """
                UNWIND $rows AS row
                MATCH (r:Role {title: row.role}), (s:Skill {name: row.skill})
                MERGE (r)-[rel:NEEDS_SKILL]->(s)
                SET rel.frequency = row.frequency,
                    rel.job_count = row.job_count,
                    rel.importance = row.importance,
                    rel.updated_at = datetime()
                """,
                rows=batch,
            )
    return role_skills


def _build_implies(db) -> None:
    # Per-skill totals
    skill_totals = {
        r[0]: int(r[1])
        for r in db.execute(
            text(
                """
                SELECT skill, COUNT(DISTINCT id)
                FROM jobs,
                     jsonb_array_elements_text(skills_required) AS skill
                WHERE status = 'active'
                GROUP BY skill
                """
            )
        )
    }
    # Co-occurrence via SQL — skill pairs per job, then aggregate
    pairs = db.execute(
        text(
            """
            WITH skill_pairs AS (
                SELECT a.skill AS skill_a, b.skill AS skill_b, j.id
                FROM jobs j,
                     jsonb_array_elements_text(j.skills_required) AS a(skill),
                     jsonb_array_elements_text(j.skills_required) AS b(skill)
                WHERE j.status = 'active'
                  AND a.skill < b.skill
            )
            SELECT skill_a, skill_b, COUNT(*) AS co
            FROM skill_pairs
            GROUP BY skill_a, skill_b
            HAVING COUNT(*) >= 10
            """
        )
    ).all()

    neo_rows = []
    for skill_a, skill_b, co in pairs:
        co = int(co)
        a_total = skill_totals.get(skill_a) or 0
        b_total = skill_totals.get(skill_b) or 0
        if a_total:
            a_implies_b = co * 100.0 / a_total
            if a_implies_b >= 60:
                neo_rows.append(
                    {
                        "a": skill_a,
                        "b": skill_b,
                        "strength": round(a_implies_b, 2),
                        "co": co,
                    }
                )
        if b_total:
            b_implies_a = co * 100.0 / b_total
            if b_implies_a >= 60:
                neo_rows.append(
                    {
                        "a": skill_b,
                        "b": skill_a,
                        "strength": round(b_implies_a, 2),
                        "co": co,
                    }
                )

    with sync_session() as session:
        for batch in _chunk(neo_rows):
            session.run(
                """
                UNWIND $rows AS row
                MATCH (a:Skill {name: row.a}), (b:Skill {name: row.b})
                MERGE (a)-[rel:IMPLIES]->(b)
                SET rel.strength = row.strength,
                    rel.co_occurrence = row.co,
                    rel.updated_at = datetime()
                """,
                rows=batch,
            )


def _build_similar(role_skills: dict[str, set[str]]) -> None:
    titles = sorted(role_skills.keys())
    neo_rows = []
    for i, t1 in enumerate(titles):
        s1 = role_skills[t1]
        if not s1:
            continue
        for t2 in titles[i + 1 :]:
            s2 = role_skills[t2]
            if not s2:
                continue
            shared = len(s1 & s2)
            if shared == 0:
                continue
            overlap = shared * 2.0 / (len(s1) + len(s2))
            if overlap < 0.5:
                continue
            neo_rows.append(
                {
                    "r1": t1,
                    "r2": t2,
                    "overlap": round(overlap, 4),
                    "shared": shared,
                }
            )

    with sync_session() as session:
        for batch in _chunk(neo_rows):
            session.run(
                """
                UNWIND $rows AS row
                MATCH (r1:Role {title: row.r1}), (r2:Role {title: row.r2})
                MERGE (r1)-[rel:SIMILAR_ROLE]->(r2)
                SET rel.overlap = row.overlap,
                    rel.shared_skill_count = row.shared,
                    rel.updated_at = datetime()
                """,
                rows=batch,
            )


def _build_uses_and_hires(db) -> None:
    company_totals = {
        r[0]: int(r[1])
        for r in db.execute(
            text(
                """
                SELECT source_company_slug, COUNT(*)
                FROM jobs WHERE status = 'active'
                GROUP BY source_company_slug
                """
            )
        )
    }
    names = {
        r[0]: r[1]
        for r in db.execute(
            text(
                """
                SELECT DISTINCT source_company_slug, company_name
                FROM jobs WHERE status = 'active'
                """
            )
        )
    }

    skill_rows = db.execute(
        text(
            """
            SELECT source_company_slug, skill, COUNT(*) AS cnt
            FROM jobs,
                 jsonb_array_elements_text(skills_required) AS skill
            WHERE status = 'active'
            GROUP BY source_company_slug, skill
            HAVING COUNT(*) >= 3
            """
        )
    ).all()

    uses = []
    for slug, skill, cnt in skill_rows:
        total = company_totals.get(slug) or 0
        if total == 0:
            continue
        pct = cnt * 100.0 / total
        if pct < 30:
            continue
        uses.append(
            {
                "slug": slug,
                "name": names.get(slug) or slug,
                "skill": skill,
                "frequency": round(pct, 2),
                "job_count": int(cnt),
            }
        )

    hire_rows = db.execute(
        text(
            """
            SELECT source_company_slug, title_normalized, COUNT(*) AS cnt
            FROM jobs
            WHERE status = 'active' AND title_normalized IS NOT NULL
            GROUP BY source_company_slug, title_normalized
            """
        )
    ).all()
    hires = [
        {
            "slug": slug,
            "name": names.get(slug) or slug,
            "role": role,
            "count": int(cnt),
        }
        for slug, role, cnt in hire_rows
    ]

    with sync_session() as session:
        # Ensure Company nodes exist
        company_nodes = [
            {"slug": slug, "name": names.get(slug) or slug}
            for slug in company_totals
        ]
        for batch in _chunk(company_nodes):
            session.run(
                """
                UNWIND $rows AS row
                MERGE (c:Company {slug: row.slug})
                ON CREATE SET c.name = row.name, c.sector = null,
                              c.active_jobs = 0, c.top_roles = [], c.primary_tech = []
                SET c.name = row.name
                """,
                rows=batch,
            )
        for batch in _chunk(uses):
            session.run(
                """
                UNWIND $rows AS row
                MATCH (c:Company {slug: row.slug}), (s:Skill {name: row.skill})
                MERGE (c)-[rel:USES]->(s)
                SET rel.frequency = row.frequency,
                    rel.job_count = row.job_count,
                    rel.updated_at = datetime()
                """,
                rows=batch,
            )
        for batch in _chunk(hires):
            session.run(
                """
                UNWIND $rows AS row
                MATCH (c:Company {slug: row.slug}), (r:Role {title: row.role})
                MERGE (c)-[rel:HIRES]->(r)
                SET rel.active_count = row.count,
                    rel.updated_at = datetime()
                """,
                rows=batch,
            )


def _build_in_location(db) -> None:
    rows = db.execute(
        text(
            """
            SELECT title_normalized, location_city, location_state, COUNT(*) AS cnt
            FROM jobs
            WHERE status = 'active'
              AND title_normalized IS NOT NULL
              AND location_city IS NOT NULL
            GROUP BY title_normalized, location_city, location_state
            HAVING COUNT(*) >= 3
            """
        )
    ).all()
    neo_rows = [
        {
            "role": title,
            "city": city,
            "state": state or "",
            "count": int(cnt),
        }
        for title, city, state, cnt in rows
    ]
    with sync_session() as session:
        loc_nodes = [
            {"city": r["city"], "state": r["state"]} for r in neo_rows
        ]
        # dedupe
        seen = set()
        unique_locs = []
        for loc in loc_nodes:
            key = (loc["city"], loc["state"])
            if key not in seen:
                seen.add(key)
                unique_locs.append(loc)
        for batch in _chunk(unique_locs):
            session.run(
                """
                UNWIND $rows AS row
                MERGE (l:Location {city: row.city, state: row.state})
                ON CREATE SET l.country = 'US', l.metro = null, l.job_count = 0
                """,
                rows=batch,
            )
        for batch in _chunk(neo_rows):
            session.run(
                """
                UNWIND $rows AS row
                MATCH (r:Role {title: row.role}),
                      (l:Location {city: row.city, state: row.state})
                MERGE (r)-[rel:IN_LOCATION]->(l)
                SET rel.job_count = row.count,
                    rel.updated_at = datetime()
                """,
                rows=batch,
            )


def _update_node_props(db) -> None:
    skill_stats = db.execute(
        text(
            """
            SELECT skill,
                   COUNT(*) AS cnt,
                   AVG(salary_min) FILTER (WHERE salary_min IS NOT NULL) AS avg_min,
                   AVG(salary_max) FILTER (WHERE salary_max IS NOT NULL) AS avg_max
            FROM jobs,
                 jsonb_array_elements_text(skills_required) AS skill
            WHERE status = 'active'
            GROUP BY skill
            """
        )
    ).all()
    role_stats = db.execute(
        text(
            """
            SELECT title_normalized,
                   COUNT(*) AS cnt,
                   AVG(salary_min) FILTER (WHERE salary_min IS NOT NULL) AS avg_min,
                   AVG(salary_max) FILTER (WHERE salary_max IS NOT NULL) AS avg_max
            FROM jobs
            WHERE status = 'active' AND title_normalized IS NOT NULL
            GROUP BY title_normalized
            """
        )
    ).all()
    company_stats = db.execute(
        text(
            """
            SELECT source_company_slug, COUNT(*) AS cnt
            FROM jobs WHERE status = 'active'
            GROUP BY source_company_slug
            """
        )
    ).all()
    loc_stats = db.execute(
        text(
            """
            SELECT location_city, COALESCE(location_state, ''), COUNT(*) AS cnt
            FROM jobs
            WHERE status = 'active' AND location_city IS NOT NULL
            GROUP BY location_city, COALESCE(location_state, '')
            """
        )
    ).all()

    with sync_session() as session:
        for batch in _chunk(
            [
                {
                    "name": s,
                    "cnt": int(c),
                    "avg_min": float(amin or 0),
                    "avg_max": float(amax or 0),
                }
                for s, c, amin, amax in skill_stats
            ]
        ):
            session.run(
                """
                UNWIND $rows AS row
                MATCH (s:Skill {name: row.name})
                SET s.job_count = row.cnt,
                    s.avg_salary_min = row.avg_min,
                    s.avg_salary_max = row.avg_max
                """,
                rows=batch,
            )
        for batch in _chunk(
            [
                {
                    "title": t,
                    "cnt": int(c),
                    "avg_min": float(amin or 0),
                    "avg_max": float(amax or 0),
                }
                for t, c, amin, amax in role_stats
            ]
        ):
            session.run(
                """
                UNWIND $rows AS row
                MATCH (r:Role {title: row.title})
                SET r.job_count = row.cnt,
                    r.avg_salary_min = row.avg_min,
                    r.avg_salary_max = row.avg_max
                """,
                rows=batch,
            )
        # top_companies per role from HIRES
        session.run(
            """
            MATCH (c:Company)-[h:HIRES]->(r:Role)
            WITH r, c, h.active_count AS cnt
            ORDER BY cnt DESC
            WITH r, collect(c.name)[0..10] AS tops
            SET r.top_companies = tops
            """
        )
        for batch in _chunk(
            [{"slug": slug, "cnt": int(c)} for slug, c in company_stats]
        ):
            session.run(
                """
                UNWIND $rows AS row
                MATCH (c:Company {slug: row.slug})
                SET c.active_jobs = row.cnt
                """,
                rows=batch,
            )
        session.run(
            """
            MATCH (c:Company)-[h:HIRES]->(r:Role)
            WITH c, r ORDER BY h.active_count DESC
            WITH c, collect(r.title)[0..10] AS roles
            SET c.top_roles = roles
            """
        )
        session.run(
            """
            MATCH (c:Company)-[u:USES]->(s:Skill)
            WHERE u.frequency >= 50
            WITH c, collect(s.name) AS tech
            SET c.primary_tech = tech
            """
        )
        for batch in _chunk(
            [
                {"city": city, "state": state, "cnt": int(c)}
                for city, state, c in loc_stats
            ]
        ):
            session.run(
                """
                UNWIND $rows AS row
                MATCH (l:Location {city: row.city, state: row.state})
                SET l.job_count = row.cnt
                """,
                rows=batch,
            )


def _enrich_skills_implied(db) -> None:
    """Load IMPLIES map once; batch-update jobs with proper JSON."""
    import json

    with sync_session() as session:
        implies = {
            r["child"]: list(r["parents"])
            for r in session.run(
                """
                MATCH (child:Skill)-[:IMPLIES]->(parent:Skill)
                RETURN child.name AS child, collect(parent.name) AS parents
                """
            )
        }

    last_id = None
    updated = 0
    while True:
        params: dict = {"lim": BATCH}
        q = "SELECT id, skills_required FROM jobs WHERE status = 'active'"
        if last_id is not None:
            q += " AND id > :last_id"
            params["last_id"] = str(last_id)
        q += " ORDER BY id LIMIT :lim"
        rows = db.execute(text(q), params).all()
        if not rows:
            break
        for job_id, skills in rows:
            required = list(skills or [])
            req_set = set(required)
            implied: set[str] = set()
            for skill in required:
                for parent in implies.get(skill, []):
                    if parent not in req_set:
                        implied.add(parent)
            db.execute(
                text(
                    "UPDATE jobs SET skills_implied = CAST(:implied AS jsonb) WHERE id = :id"
                ),
                {"id": job_id, "implied": json.dumps(sorted(implied))},
            )
        db.commit()
        updated += len(rows)
        last_id = rows[-1][0]
    logger.info("skills_implied_enriched", jobs=updated)


def build_graph_relationships_impl() -> dict:
    started = time.monotonic()
    with sync_session() as session:
        session.run(_CLEAR_RELS)

    with get_sync_db() as db:
        role_skills = _build_needs_skill(db)
        _build_implies(db)
        _build_similar(role_skills)
        _build_uses_and_hires(db)
        _build_in_location(db)
        _update_node_props(db)
        _enrich_skills_implied(db)

    with sync_session() as session:
        session.run(
            """
            MERGE (m:GraphMeta {id: 'singleton'})
            SET m.last_built_at = datetime()
            """
        )
        counts = {
            r["type"]: r["n"]
            for r in session.run(
                """
                MATCH ()-[r]->()
                RETURN type(r) AS type, count(r) AS n
                """
            )
        }

    duration = time.monotonic() - started
    summary = {
        "counts": counts,
        "duration_s": round(duration, 1),
    }
    logger.info(
        "graph_built",
        skill_edges=counts.get("IMPLIES", 0) + counts.get("NEEDS_SKILL", 0),
        role_edges=counts.get("SIMILAR_ROLE", 0) + counts.get("IN_LOCATION", 0),
        company_edges=counts.get("USES", 0) + counts.get("HIRES", 0),
        duration_s=summary["duration_s"],
    )
    print(
        f"Graph built: {counts}. Duration: {summary['duration_s']}s",
        flush=True,
    )
    return summary


@celery_app.task(name="src.workers.graph_builder.build_graph_relationships")
def build_graph_relationships() -> dict:
    return build_graph_relationships_impl()
