"""Market intelligence queries over Neo4j + Postgres."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.errors import (
    CompanyNotFoundError,
    GraphUnavailableError,
    RoleNotFoundError,
    SkillNotFoundError,
)
from src.graph.connection import is_available, sync_session
from src.graph.queries import graph_age_hours
from src.services.data_loader import DataLoader
from src.services.extractors.title import normalize_title


def _stale_warning() -> str | None:
    age = graph_age_hours()
    if age is not None and age > 6:
        return f"Data may be stale. Last graph update was {age:.0f} hours ago."
    return None


def _data_source(n: int, noun: str = "live job postings") -> str:
    age = graph_age_hours()
    age_txt = f"{age:.0f} hours ago" if age is not None else "unknown"
    return f"Computed from {n:,} {noun}. Last updated {age_txt}."


def _resolve_role(role: str) -> str | None:
    data = DataLoader.get()
    canonical = data.title_alias_index.get(role.strip().lower())
    if canonical:
        return canonical
    title, _ = normalize_title(role, data.taxonomy)
    return title


def _resolve_skill(skill: str) -> tuple[str, str] | None:
    data = DataLoader.get()
    lower = skill.strip().lower()
    for entry in data.skills:
        if entry["canonical"].lower() == lower:
            return entry["canonical"], entry.get("category") or ""
        for alias in entry.get("aliases") or []:
            if alias.lower() == lower:
                return entry["canonical"], entry.get("category") or ""
    return None


def get_role_insights(db: Session, role: str) -> dict:
    if not is_available():
        raise GraphUnavailableError()
    title = _resolve_role(role)
    if not title:
        raise RoleNotFoundError(detail=f"Role not found: {role}")

    with sync_session() as session:
        node = session.run(
            """
            MATCH (r:Role {title: $title})
            RETURN r.function AS function, r.job_count AS job_count,
                   r.avg_salary_min AS avg_min, r.avg_salary_max AS avg_max
            """,
            title=title,
        ).single()
        if node is None:
            raise RoleNotFoundError(detail=f"Role not found: {role}")

        needs = list(
            session.run(
                """
                MATCH (r:Role {title: $title})-[rel:NEEDS_SKILL]->(s:Skill)
                RETURN s.name AS name, rel.frequency AS frequency,
                       rel.importance AS importance
                ORDER BY rel.frequency DESC
                """,
                title=title,
            )
        )
        companies = list(
            session.run(
                """
                MATCH (c:Company)-[h:HIRES]->(r:Role {title: $title})
                RETURN c.name AS name, h.active_count AS active_jobs
                ORDER BY h.active_count DESC
                LIMIT 10
                """,
                title=title,
            )
        )
        locations = list(
            session.run(
                """
                MATCH (r:Role {title: $title})-[rel:IN_LOCATION]->(l:Location)
                RETURN l.city AS city, l.state AS state, rel.job_count AS job_count
                ORDER BY rel.job_count DESC
                LIMIT 10
                """,
                title=title,
            )
        )
        similar = list(
            session.run(
                """
                MATCH (r:Role {title: $title})-[rel:SIMILAR_ROLE]-(s:Role)
                RETURN s.title AS title, rel.overlap AS overlap, s.job_count AS active_jobs
                ORDER BY rel.overlap DESC
                LIMIT 10
                """,
                title=title,
            )
        )

    core, common, occasional = [], [], []
    for n in needs:
        item = {
            "name": n["name"],
            "frequency": n["frequency"],
            "importance": n["importance"],
        }
        if n["importance"] == "core":
            core.append(item)
        elif n["importance"] == "common":
            common.append(item)
        else:
            occasional.append(item)

    # Postgres breakdowns
    remote_rows = db.execute(
        text(
            """
            SELECT remote_policy, COUNT(*) FROM jobs
            WHERE status = 'active' AND title_normalized = :t
            GROUP BY remote_policy
            """
        ),
        {"t": title},
    ).all()
    sen_rows = db.execute(
        text(
            """
            SELECT seniority, COUNT(*) FROM jobs
            WHERE status = 'active' AND title_normalized = :t AND seniority IS NOT NULL
            GROUP BY seniority
            """
        ),
        {"t": title},
    ).all()
    total = int(node["job_count"] or 0) or sum(int(c) for _, c in remote_rows)

    def _pct_map(rows) -> dict:
        s = sum(int(c) for _, c in rows) or 1
        return {k or "unknown": round(100 * int(c) / s) for k, c in rows}

    amin = int(node["avg_min"] or 0)
    amax = int(node["avg_max"] or 0)
    out = {
        "role": title,
        "function": node["function"] or "",
        "total_active_jobs": total,
        "salary": {
            "avg_min": amin,
            "avg_max": amax,
            "formatted": f"${amin:,} - ${amax:,} average" if amin or amax else "n/a",
        },
        "core_skills": core,
        "common_skills": common,
        "occasional_skills": occasional,
        "top_hiring_companies": [
            {"name": c["name"], "active_jobs": int(c["active_jobs"] or 0)}
            for c in companies
        ],
        "top_locations": [
            {
                "city": loc["city"],
                "state": loc["state"],
                "job_count": int(loc["job_count"] or 0),
            }
            for loc in locations
        ],
        "similar_roles": [
            {
                "title": s["title"],
                "overlap": s["overlap"],
                "active_jobs": int(s["active_jobs"] or 0),
            }
            for s in similar
        ],
        "remote_breakdown": _pct_map(remote_rows),
        "seniority_breakdown": _pct_map(sen_rows),
        "data_source": _data_source(total),
    }
    warning = _stale_warning()
    if warning:
        out["warning"] = warning
    return out


def get_skill_insights(db: Session, skill: str) -> dict:
    if not is_available():
        raise GraphUnavailableError()
    resolved = _resolve_skill(skill)
    if not resolved:
        raise SkillNotFoundError(detail=f"Skill not found: {skill}")
    name, category = resolved

    with sync_session() as session:
        node = session.run(
            """
            MATCH (s:Skill {name: $name})
            RETURN s.job_count AS job_count, s.avg_salary_min AS avg_min,
                   s.avg_salary_max AS avg_max
            """,
            name=name,
        ).single()
        if node is None:
            raise SkillNotFoundError(detail=f"Skill not found: {skill}")

        top_roles = list(
            session.run(
                """
                MATCH (r:Role)-[rel:NEEDS_SKILL]->(s:Skill {name: $name})
                RETURN r.title AS title, rel.frequency AS frequency,
                       rel.importance AS importance
                ORDER BY rel.frequency DESC
                LIMIT 10
                """,
                name=name,
            )
        )
        implies_knowledge = list(
            session.run(
                """
                MATCH (c:Skill)-[rel:IMPLIES]->(s:Skill {name: $name})
                RETURN c.name AS skill, rel.strength AS strength
                ORDER BY rel.strength DESC
                LIMIT 15
                """,
                name=name,
            )
        )
        paired = list(
            session.run(
                """
                MATCH (s:Skill {name: $name})-[rel:IMPLIES]-(other:Skill)
                RETURN other.name AS skill, rel.co_occurrence AS co_occurrence,
                       rel.strength AS strength
                ORDER BY rel.co_occurrence DESC
                LIMIT 10
                """,
                name=name,
            )
        )
        companies = list(
            session.run(
                """
                MATCH (c:Company)-[u:USES]->(s:Skill {name: $name})
                RETURN c.name AS name, u.job_count AS job_count
                ORDER BY u.job_count DESC
                LIMIT 10
                """,
                name=name,
            )
        )

    amin = int(node["avg_min"] or 0)
    amax = int(node["avg_max"] or 0)
    total = int(node["job_count"] or 0)
    out = {
        "skill": name,
        "category": category,
        "total_jobs_requiring": total,
        "salary_impact": {
            "avg_min_with": amin,
            "avg_max_with": amax,
            "formatted": f"Jobs requiring {name} average ${amin:,}-${amax:,}",
        },
        "top_roles": [
            {
                "title": r["title"],
                "frequency": r["frequency"],
                "importance": r["importance"],
            }
            for r in top_roles
        ],
        "commonly_paired_with": [
            {"skill": p["skill"], "co_occurrence": int(p["co_occurrence"] or 0)}
            for p in paired
        ],
        "implies_knowledge_of": [
            {"skill": i["skill"], "strength": i["strength"]}
            for i in implies_knowledge
        ],
        "top_companies": [
            {"name": c["name"], "job_count": int(c["job_count"] or 0)}
            for c in companies
        ],
        "data_source": _data_source(total),
    }
    warning = _stale_warning()
    if warning:
        out["warning"] = warning
    return out


def get_company_stack(db: Session, company: str) -> dict:
    if not is_available():
        raise GraphUnavailableError()
    q = company.strip()

    with sync_session() as session:
        node = session.run(
            """
            MATCH (c:Company)
            WHERE toLower(c.name) = toLower($q) OR toLower(c.slug) = toLower($q)
               OR toLower(c.name) CONTAINS toLower($q)
            RETURN c.name AS name, c.slug AS slug, c.sector AS sector,
                   c.active_jobs AS active_jobs
            ORDER BY CASE WHEN toLower(c.name) = toLower($q) THEN 0 ELSE 1 END
            LIMIT 1
            """,
            q=q,
        ).single()
        if node is None:
            raise CompanyNotFoundError(detail=f"Company not found: {company}")

        slug = node["slug"]
        uses = list(
            session.run(
                """
                MATCH (c:Company {slug: $slug})-[u:USES]->(s:Skill)
                RETURN s.name AS skill, u.frequency AS frequency, u.job_count AS job_count
                ORDER BY u.frequency DESC
                """,
                slug=slug,
            )
        )
        hires = list(
            session.run(
                """
                MATCH (c:Company {slug: $slug})-[h:HIRES]->(r:Role)
                RETURN r.title AS title, h.active_count AS count
                ORDER BY h.active_count DESC
                """,
                slug=slug,
            )
        )
        # Similar companies by USES Jaccard
        my_skills = {u["skill"] for u in uses}
        others = list(
            session.run(
                """
                MATCH (c:Company)-[:USES]->(s:Skill)
                WHERE c.slug <> $slug
                RETURN c.name AS name, collect(s.name) AS skills
                """,
                slug=slug,
            )
        )

    primary, secondary = [], []
    for u in uses:
        item = {
            "skill": u["skill"],
            "frequency": u["frequency"],
            "job_count": int(u["job_count"] or 0),
        }
        if (u["frequency"] or 0) >= 50:
            primary.append(item)
        elif (u["frequency"] or 0) >= 30:
            secondary.append(item)

    similar = []
    if my_skills:
        for o in others:
            other_set = set(o["skills"] or [])
            if not other_set:
                continue
            overlap = len(my_skills & other_set) / len(my_skills | other_set)
            if overlap > 0:
                similar.append({"name": o["name"], "tech_overlap": round(overlap, 2)})
        similar.sort(key=lambda x: x["tech_overlap"], reverse=True)
        similar = similar[:5]

    loc_rows = db.execute(
        text(
            """
            SELECT
              CASE WHEN remote_policy = 'remote' THEN 'Remote'
                   ELSE COALESCE(location_city, 'Unknown') END AS city,
              COUNT(*) AS cnt
            FROM jobs
            WHERE status = 'active' AND source_company_slug = :slug
            GROUP BY 1
            ORDER BY cnt DESC
            LIMIT 10
            """
        ),
        {"slug": slug},
    ).all()
    sen_rows = db.execute(
        text(
            """
            SELECT seniority, COUNT(*) FROM jobs
            WHERE status = 'active' AND source_company_slug = :slug
              AND seniority IS NOT NULL
            GROUP BY seniority
            """
        ),
        {"slug": slug},
    ).all()

    active = int(node["active_jobs"] or 0)
    out = {
        "company": node["name"],
        "sector": node["sector"],
        "active_jobs": active,
        "tech_stack": {"primary": primary, "secondary": secondary},
        "hiring_by_role": [
            {"title": h["title"], "count": int(h["count"] or 0)} for h in hires
        ],
        "hiring_by_location": [
            {"city": city, "count": int(cnt)} for city, cnt in loc_rows
        ],
        "hiring_by_seniority": {k: int(c) for k, c in sen_rows},
        "similar_companies_by_tech": similar,
        "data_source": _data_source(active, "active job postings"),
    }
    warning = _stale_warning()
    if warning:
        out["warning"] = warning
    return out


def graph_stats_block() -> dict | None:
    if not is_available():
        return None
    try:
        with sync_session() as session:
            counts = {
                r["type"]: r["n"]
                for r in session.run(
                    "MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS n"
                )
            }
            top_impl = [
                {
                    "from": r["a"],
                    "to": r["b"],
                    "strength": r["strength"],
                }
                for r in session.run(
                    """
                    MATCH (a:Skill)-[rel:IMPLIES]->(b:Skill)
                    RETURN a.name AS a, b.name AS b, rel.strength AS strength
                    ORDER BY rel.strength DESC LIMIT 5
                    """
                )
            ]
            top_sim = [
                {
                    "a": r["a"],
                    "b": r["b"],
                    "overlap": r["overlap"],
                }
                for r in session.run(
                    """
                    MATCH (a:Role)-[rel:SIMILAR_ROLE]->(b:Role)
                    RETURN a.title AS a, b.title AS b, rel.overlap AS overlap
                    ORDER BY rel.overlap DESC LIMIT 5
                    """
                )
            ]
            age = graph_age_hours()
            return {
                "relationship_counts": counts,
                "last_built_at_age_hours": age,
                "top_implications": top_impl,
                "top_similar_roles": top_sim,
            }
    except Exception:
        return None
