"""analyze_skills + get_skill_gaps helpers."""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from src.graph.connection import is_available, sync_session
from src.models.job import Job
from src.schemas.matching import ExpandedSkillProfile
from src.services.data_loader import DataLoader
from src.services.job_service import _resolve_query_role, _resolve_skill_canonical
from src.services.matching.skill_expander import expand_user_skills


def _profile_names(profile: ExpandedSkillProfile) -> set[str]:
    return {s.name for s in profile.all_skills}


def analyze_skills(db: Session, skills: list[str]) -> dict:
    profile = expand_user_skills(skills)
    names = _profile_names(profile)
    warning = None
    best_roles: list[dict] = []

    if is_available():
        try:
            with sync_session() as session:
                roles = list(
                    session.run(
                        """
                        MATCH (r:Role)
                        WHERE r.job_count > 0
                        RETURN r.title AS title, r.job_count AS job_count,
                               r.avg_salary_min AS amin, r.avg_salary_max AS amax
                        ORDER BY r.job_count DESC
                        LIMIT 30
                        """
                    )
                )
                for role in roles:
                    title = role["title"]
                    core = [
                        r["name"]
                        for r in session.run(
                            """
                            MATCH (r:Role {title: $title})-[rel:NEEDS_SKILL]->(s:Skill)
                            WHERE rel.importance = 'core' OR rel.frequency >= 0.4
                            RETURN s.name AS name
                            ORDER BY rel.frequency DESC
                            LIMIT 12
                            """,
                            title=title,
                        )
                    ]
                    if not core:
                        continue
                    have = [s for s in core if s in names]
                    missing = [s for s in core if s not in names]
                    pct = int(round(100 * len(have) / len(core)))
                    best_roles.append(
                        {
                            "role": title,
                            "match_percent": pct,
                            "active_jobs": int(role["job_count"] or 0),
                            "avg_salary_min": int(role["amin"] or 0) or None,
                            "avg_salary_max": int(role["amax"] or 0) or None,
                            "skills_you_have": have,
                            "missing_core_skills": missing,
                        }
                    )
        except Exception:
            warning = "Graph query failed; using Postgres-only skill analysis."
    else:
        warning = "Neo4j unavailable; using Postgres-only skill analysis."

    if not best_roles:
        # Postgres fallback: count jobs containing any user skill
        for sk in list(names)[:10]:
            count = (
                db.scalar(
                    select(func.count())
                    .select_from(Job)
                    .where(
                        Job.status == "active",
                        or_(
                            Job.skills_required.contains([sk]),
                            Job.skills_implied.contains([sk]),
                        ),
                    )
                )
                or 0
            )
            best_roles.append(
                {
                    "role": f"Jobs mentioning {sk}",
                    "match_percent": 100,
                    "active_jobs": int(count),
                    "missing_core_skills": [],
                    "skills_you_have": [sk],
                }
            )

    best_roles.sort(key=lambda r: (-r["match_percent"], -r.get("active_jobs", 0)))
    total_jobs = sum(r.get("active_jobs", 0) for r in best_roles[:10])
    return {
        "your_skills": {
            "direct": [s.name for s in profile.direct],
            "inferred": [s.name for s in profile.inferred],
        },
        "best_fitting_roles": best_roles[:15],
        "market_insight": {
            "roles_analyzed": len(best_roles),
            "approx_matching_jobs": total_jobs,
            "strongest_skill": profile.direct[0].name if profile.direct else None,
        },
        "warning": warning,
    }


def get_skill_gaps(db: Session, skills: list[str], target_role: str) -> dict:
    profile = expand_user_skills(skills)
    names = _profile_names(profile)
    data = DataLoader.get()
    canonical = _resolve_query_role(target_role, data) or target_role.strip()

    core: list[tuple[str, float]] = []
    if is_available():
        try:
            with sync_session() as session:
                core = [
                    (r["name"], float(r["freq"] or 0))
                    for r in session.run(
                        """
                        MATCH (r:Role {title: $title})-[rel:NEEDS_SKILL]->(s:Skill)
                        RETURN s.name AS name, rel.frequency AS freq
                        ORDER BY rel.frequency DESC
                        LIMIT 40
                        """,
                        title=canonical,
                    )
                ]
        except Exception:
            core = []

    if not core:
        # Fallback: top skills from active jobs with this title
        rows = db.execute(
            select(Job.skills_required)
            .where(Job.status == "active", Job.title_normalized == canonical)
            .limit(200)
        ).all()
        from collections import Counter

        c: Counter[str] = Counter()
        for (req,) in rows:
            for s in req or []:
                c[s] += 1
        total = max(sum(c.values()), 1)
        core = [(s, n / total) for s, n in c.most_common(30)]

    have, close, need = [], [], []
    for skill, freq in core:
        canon = _resolve_skill_canonical(skill, data)
        if canon in names or skill in names:
            have.append({"skill": canon, "demanded_in": round(freq, 3)})
            continue
        # close = in lateral/inferred neighborhood already handled; else need
        near = any(
            s.name == canon and s.source in {"inferred", "lateral"}
            for s in profile.all_skills
        )
        entry = {"skill": canon, "demanded_in": round(freq, 3)}
        if near:
            close.append(entry)
        else:
            # salary impact
            with_sk = db.scalar(
                select(func.avg(Job.salary_max)).where(
                    Job.status == "active",
                    Job.title_normalized == canonical,
                    Job.skills_required.contains([canon]),
                    Job.salary_max.is_not(None),
                )
            )
            without = db.scalar(
                select(func.avg(Job.salary_max)).where(
                    Job.status == "active",
                    Job.title_normalized == canonical,
                    Job.salary_max.is_not(None),
                )
            )
            entry["salary_impact"] = {
                "avg_with_skill": int(with_sk) if with_sk else None,
                "avg_role_overall": int(without) if without else None,
            }
            need.append(entry)

    quick_wins = close[:3] or need[:1]
    return {
        "target_role": canonical,
        "skills_you_have": have,
        "skills_youre_close_to": close,
        "skills_you_need": need,
        "quick_wins": quick_wins,
    }
