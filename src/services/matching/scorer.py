"""Per-job match scoring against an expanded skill profile."""
from __future__ import annotations

from datetime import UTC, datetime

from src.graph.queries import role_overlap
from src.models.job import Job
from src.schemas.matching import (
    ExpandedSkillProfile,
    MatchScore,
    SkillMatch,
    SkillWithConfidence,
)
from src.services.data_loader import DataLoader
from src.services.job_service import (
    _resolve_location_filter,
    _resolve_query_role,
    _resolve_skill_canonical,
)


def _profile_index(
    profile: ExpandedSkillProfile,
) -> dict[str, SkillWithConfidence]:
    return {s.name: s for s in profile.all_skills}


def _skill_score(
    skill: str, index: dict[str, SkillWithConfidence]
) -> tuple[float, SkillMatch | None]:
    data = DataLoader.get()
    name = _resolve_skill_canonical(skill, data)
    hit = index.get(name) or index.get(skill)
    if hit is None:
        return 0.0, None
    return hit.confidence, SkillMatch(
        skill=hit.name,
        match_type=hit.source,
        confidence=hit.confidence,
        inferred_from=hit.inferred_from,
    )


def _skills_fit(
    profile: ExpandedSkillProfile, job: Job
) -> tuple[int, list[SkillMatch], list[str], list[str]]:
    index = _profile_index(profile)
    required = list(job.skills_required or [])
    nice = list(job.skills_nice_to_have or [])
    matched: list[SkillMatch] = []
    missing: list[str] = []
    inferred_used: list[str] = []

    if not required:
        req_score = 1.0
    else:
        scores = []
        for sk in required:
            conf, sm = _skill_score(sk, index)
            scores.append(conf)
            if sm is None:
                missing.append(sk)
            else:
                matched.append(sm)
                if sm.match_type in {"inferred", "lateral"}:
                    inferred_used.append(sm.skill)
        req_score = sum(scores) / len(scores)

    if not nice:
        total = req_score
    else:
        nice_scores = []
        for sk in nice:
            conf, sm = _skill_score(sk, index)
            nice_scores.append(conf)
            if sm is not None:
                matched.append(sm)
                if sm.match_type in {"inferred", "lateral"}:
                    inferred_used.append(sm.skill)
        nice_fit = sum(nice_scores) / len(nice_scores)
        total = req_score * 0.75 + nice_fit * 0.25

    return (
        int(round(total * 100)),
        matched,
        missing,
        list(dict.fromkeys(inferred_used)),
    )


def _role_fit(target_role: str | None, job: Job) -> int:
    if not target_role:
        return 50
    data = DataLoader.get()
    canonical = _resolve_query_role(target_role, data) or target_role.strip()
    job_title = job.title_normalized or job.title_raw
    if job_title == canonical:
        return 100
    overlap = role_overlap(canonical, job_title)
    if overlap is not None and overlap >= 0.6:
        return int(round(overlap * 100))
    return 30


def _location_pref(
    job: Job, location: str | None, remote_ok: bool, locations: dict
) -> float:
    if not location:
        return 1.0
    city, metro, is_remote, loc_country = _resolve_location_filter(location, locations)
    if is_remote or location.strip().lower() == "remote":
        return 1.0 if job.remote_policy in {"remote", "hybrid"} else 0.0
    if loc_country:
        return 1.0 if (job.location_country or "").upper() == loc_country else 0.0
    if remote_ok and job.remote_policy in {"remote", "hybrid"}:
        return 1.0
    job_city = (job.location_city or "").lower()
    job_metro = (job.location_metro or "").lower()
    if city and city.lower() in {job_city, job_metro}:
        return 1.0
    if metro and metro.lower() == job_metro:
        return 1.0
    if city and city.lower() in (job.location_state or "").lower():
        return 1.0
    return 0.0


def _preference_fit(
    job: Job,
    *,
    location: str | None,
    remote_ok: bool,
    salary_min: int | None,
    experience_years: int | None,
    visa_needed: bool,
    locations: dict,
) -> int:
    loc = _location_pref(job, location, remote_ok, locations)
    if salary_min is None:
        sal = 1.0
    elif job.salary_max is None and job.salary_min is None:
        sal = 1.0
    elif job.salary_max is not None and job.salary_max >= salary_min:
        sal = 1.0
    else:
        sal = 0.0

    if experience_years is None:
        exp = 1.0
    elif job.experience_min is None or job.experience_min <= experience_years:
        exp = 1.0
    else:
        exp = 0.0

    if not visa_needed:
        visa = 1.0
    elif job.visa_sponsorship == "sponsors":
        visa = 1.0
    else:
        visa = 0.0

    return int(round(((loc + sal + exp + visa) / 4) * 100))


def _freshness(job: Job) -> int:
    ts = job.first_seen_at
    if ts is None:
        return 10
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    hours = (datetime.now(UTC) - ts).total_seconds() / 3600.0
    if hours < 24:
        return 100
    if hours < 72:
        return 70
    if hours < 168:
        return 40
    return 10


def score_match(
    profile: ExpandedSkillProfile,
    job: Job,
    *,
    target_role: str | None = None,
    location: str | None = None,
    remote_ok: bool = True,
    salary_min: int | None = None,
    experience_years: int | None = None,
    visa_needed: bool = False,
    locations: dict | None = None,
) -> MatchScore:
    locs = locations if locations is not None else DataLoader.get().locations
    skills_fit, matched, missing, inferred_used = _skills_fit(profile, job)
    role = _role_fit(target_role, job)
    pref = _preference_fit(
        job,
        location=location,
        remote_ok=remote_ok,
        salary_min=salary_min,
        experience_years=experience_years,
        visa_needed=visa_needed,
        locations=locs,
    )
    fresh = _freshness(job)
    overall = int(
        round(
            skills_fit * 0.50
            + role * 0.20
            + pref * 0.20
            + fresh * 0.10
        )
    )
    explanation = {
        "top_matched": [m.skill for m in matched[:5]],
        "top_missing": missing[:5],
        "role_fit_note": "neutral" if not target_role else ("exact" if role == 100 else "partial"),
        "preference_misses": [],
    }
    if location and pref < 100:
        explanation["preference_misses"].append("location_or_prefs")
    return MatchScore(
        overall=overall,
        skills_fit=skills_fit,
        role_fit=role,
        preference_fit=pref,
        freshness=fresh,
        matched_skills=matched,
        missing_skills=missing,
        inferred_skills_used=inferred_used,
        explanation=explanation,
    )
