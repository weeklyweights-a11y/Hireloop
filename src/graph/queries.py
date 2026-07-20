"""Neo4j read helpers for search expansion and role insights."""
from __future__ import annotations

from src.graph.connection import is_available, sync_session


def role_overlap(user_role: str, job_title: str) -> float | None:
    """Return SIMILAR_ROLE.overlap for two titles, 1.0 if exact, else None."""
    if not user_role or not job_title:
        return None
    if user_role == job_title:
        return 1.0
    if not is_available():
        return None
    try:
        with sync_session() as session:
            rec = session.run(
                """
                MATCH (a:Role {title: $a})-[rel:SIMILAR_ROLE]-(b:Role {title: $b})
                RETURN rel.overlap AS overlap
                LIMIT 1
                """,
                a=user_role,
                b=job_title,
            ).single()
            if rec is None:
                return None
            return float(rec["overlap"] or 0)
    except Exception:
        return None


def expand_skills(skill_name: str) -> list[str]:
    """Return skill_name plus skills that IMPLY it (Flask → Python)."""
    if not skill_name or not is_available():
        return [skill_name] if skill_name else []
    try:
        with sync_session() as session:
            result = session.run(
                """
                MATCH (s:Skill {name: $name})<-[:IMPLIES]-(child:Skill)
                RETURN child.name AS name
                """,
                name=skill_name,
            )
            children = [r["name"] for r in result]
        out = [skill_name]
        for c in children:
            if c not in out:
                out.append(c)
        return out
    except Exception:
        return [skill_name]


def expand_roles(title: str, min_overlap: float = 0.6) -> list[str]:
    """Return similar role titles with SIMILAR_ROLE.overlap >= min_overlap."""
    if not title or not is_available():
        return []
    try:
        with sync_session() as session:
            result = session.run(
                """
                MATCH (r:Role {title: $title})-[rel:SIMILAR_ROLE]-(similar:Role)
                WHERE rel.overlap >= $min_overlap
                RETURN similar.title AS title
                """,
                title=title,
                min_overlap=min_overlap,
            )
            return [r["title"] for r in result]
    except Exception:
        return []


def role_insights_for_title(title: str) -> dict | None:
    if not title or not is_available():
        return None
    try:
        with sync_session() as session:
            role = session.run(
                """
                MATCH (r:Role {title: $title})
                RETURN r.job_count AS job_count,
                       r.avg_salary_min AS avg_min,
                       r.avg_salary_max AS avg_max
                """,
                title=title,
            ).single()
            if role is None:
                return None
            skills = [
                r["name"]
                for r in session.run(
                    """
                    MATCH (r:Role {title: $title})-[rel:NEEDS_SKILL]->(s:Skill)
                    RETURN s.name AS name
                    ORDER BY rel.frequency DESC
                    LIMIT 8
                    """,
                    title=title,
                )
            ]
            similar = [
                r["title"]
                for r in session.run(
                    """
                    MATCH (r:Role {title: $title})-[rel:SIMILAR_ROLE]-(s:Role)
                    WHERE rel.overlap >= 0.5
                    RETURN s.title AS title
                    ORDER BY rel.overlap DESC
                    LIMIT 5
                    """,
                    title=title,
                )
            ]
            amin = int(role["avg_min"] or 0)
            amax = int(role["avg_max"] or 0)
            avg_salary = None
            if amin or amax:
                if amin and amax:
                    avg_salary = f"${amin:,} - ${amax:,}"
                elif amin:
                    avg_salary = f"${amin:,}+"
                else:
                    avg_salary = f"up to ${amax:,}"
            return {
                "total_jobs_for_role": int(role["job_count"] or 0),
                "avg_salary": avg_salary,
                "top_skills": skills,
                "similar_roles": similar,
            }
    except Exception:
        return None


def graph_age_hours() -> float | None:
    if not is_available():
        return None
    try:
        with sync_session() as session:
            rec = session.run(
                """
                MATCH (m:GraphMeta {id: 'singleton'})
                RETURN m.last_built_at AS ts
                """
            ).single()
            if rec is None or rec["ts"] is None:
                return None
            # neo4j DateTime → epoch
            ts = rec["ts"]
            from datetime import UTC, datetime

            built = datetime.fromtimestamp(ts.to_native().timestamp(), tz=UTC)
            return (datetime.now(UTC) - built).total_seconds() / 3600.0
    except Exception:
        return None
