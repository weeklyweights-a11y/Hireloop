"""Batch job matcher: SQL pre-filter + score + gaps."""
from __future__ import annotations

from collections import Counter, defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.graph.connection import is_available, sync_session
from src.graph.queries import expand_roles
from src.models.job import Job
from src.schemas.matching import (
    ExpandedSkillProfile,
    JobMatch,
    MatchFilters,
    MatchResult,
    SkillGap,
    clamp_match_limit,
)
from src.services.data_loader import DataLoader
from src.services.job_service import (
    _apply_job_filters,
    _data_freshness,
    _resolve_query_role,
    job_to_summary,
)
from src.services.matching.scorer import score_match
from src.services.matching.skill_expander import expand_user_skills

MAX_MATCH_CANDIDATES = 2000
MIN_OVERALL = 30


def _profile_summary(profile: ExpandedSkillProfile) -> dict:
    return {
        "direct_skills": [s.name for s in profile.direct],
        "inferred_skills": [
            {"skill": s.name, "confidence": s.confidence, "from": s.inferred_from}
            for s in profile.inferred
        ],
        "lateral_skills": [
            {"skill": s.name, "confidence": s.confidence, "from": s.inferred_from}
            for s in profile.lateral
        ],
        "total_skills_used": len(profile.all_skills),
    }


def _learn_path(missing: str, user_direct: list[str]) -> list[str] | None:
    if not user_direct or not is_available():
        return None
    try:
        with sync_session() as session:
            rows = session.run(
                """
                MATCH (missing:Skill {name: $missing})-[r:IMPLIES]-(related:Skill)
                WHERE related.name IN $user_skills
                RETURN related.name AS name, r.strength AS strength
                ORDER BY r.strength DESC
                LIMIT 3
                """,
                missing=missing,
                user_skills=user_direct,
            )
            paths = []
            for r in rows:
                strength = float(r["strength"] or 0)
                label = "closely related" if strength >= 80 else "related"
                paths.append(f"{r['name']} → {missing} ({label})")
            return paths or None
    except Exception:
        return None


def _skill_importance(skill: str, role_titles: list[str]) -> str:
    if not role_titles or not is_available():
        return "common"
    try:
        with sync_session() as session:
            rec = session.run(
                """
                MATCH (r:Role)-[rel:NEEDS_SKILL]->(s:Skill {name: $skill})
                WHERE r.title IN $roles
                RETURN rel.importance AS importance, rel.frequency AS freq
                ORDER BY rel.frequency DESC
                LIMIT 1
                """,
                skill=skill,
                roles=role_titles,
            ).single()
            if rec and rec["importance"]:
                return str(rec["importance"])
    except Exception:
        pass
    return "common"


def _aggregate_gaps(
    matches: list[JobMatch], profile: ExpandedSkillProfile
) -> list[SkillGap]:
    if not matches:
        return []
    n = len(matches)
    freq: Counter[str] = Counter()
    roles: dict[str, set[str]] = defaultdict(set)
    for m in matches:
        title = m.job.title_normalized or m.job.title
        for sk in m.score.missing_skills:
            freq[sk] += 1
            roles[sk].add(title)
    direct = [s.name for s in profile.direct]
    gaps: list[SkillGap] = []
    for skill, count in freq.most_common(20):
        role_list = sorted(roles[skill])
        gaps.append(
            SkillGap(
                skill=skill,
                frequency=round(count / n, 3),
                importance=_skill_importance(skill, role_list),
                roles_needing=role_list[:5],
                learn_path=_learn_path(skill, direct),
                missing_in=f"missing in {int(round(100 * count / n))}% of your matches",
            )
        )
    return gaps


def match_jobs(
    db: Session,
    skills: list[str],
    filters: MatchFilters | None = None,
    *,
    profile: ExpandedSkillProfile | None = None,
) -> MatchResult:
    filters = filters or MatchFilters()
    limit = clamp_match_limit(filters.limit)
    offset = max(0, int(filters.offset or 0))
    profile = profile or expand_user_skills(skills)
    data = DataLoader.get()

    title_in: list[str] | None = None
    if filters.target_role:
        canonical = _resolve_query_role(filters.target_role, data)
        if canonical:
            similar = expand_roles(canonical, min_overlap=0.6)
            title_in = [canonical, *similar]

    stmt = _apply_job_filters(
        select(Job),
        locations=data.locations,
        location=filters.location,
        company_names=filters.companies or None,
        remote_ok=filters.remote_ok,
        experience_years=filters.experience_years,
        salary_min=filters.salary_min,
        seniority=filters.seniority,
        visa_needed=filters.visa_needed,
        title_normalized_in=title_in,
        posted_within_hours=filters.posted_within_hours,
    )
    candidates = list(db.scalars(stmt.limit(MAX_MATCH_CANDIDATES)).all())

    scored: list[JobMatch] = []
    for job in candidates:
        score = score_match(
            profile,
            job,
            target_role=filters.target_role,
            location=filters.location,
            remote_ok=filters.remote_ok,
            salary_min=filters.salary_min,
            experience_years=filters.experience_years,
            visa_needed=filters.visa_needed,
            locations=data.locations,
        )
        if score.overall < MIN_OVERALL:
            continue
        summary = job_to_summary(job)
        scored.append(
            JobMatch(
                job=summary,
                score=score,
                skills_analysis={
                    "matched": [m.model_dump() for m in score.matched_skills],
                    "missing": score.missing_skills,
                    "inferred_used": score.inferred_skills_used,
                },
            )
        )

    scored.sort(key=lambda m: (-m.score.overall, m.job.title))
    top = scored[offset : offset + limit]
    # Gaps from the full ranked set (not just this page) so paging stays consistent.
    gaps = _aggregate_gaps(scored, profile)
    return MatchResult(
        total_matches=len(scored),
        showing=len(top),
        matches=top,
        skill_gaps=gaps,
        profile_summary=_profile_summary(profile),
        data_freshness=_data_freshness(db),
    )
