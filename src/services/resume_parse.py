"""Heuristic resume text → skills profile (no LLM)."""

from __future__ import annotations

import re

from src.services.data_loader import DataLoader
from src.services.extractors.skills import extract_skills
from src.services.matching.skill_expander import expand_user_skills

_EMAIL = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_LINKEDIN = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w%-]+/?", re.I)
_GITHUB = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[\w-]+/?", re.I)
_YEARS = re.compile(
    r"(?:(\d+)\+?\s*(?:years?|yrs?)(?:\s+of\s+experience)?|"
    r"(?:experience|exp)[:\s]+(\d+)\+?\s*(?:years?|yrs?))",
    re.I,
)
_ROLE_AT = re.compile(
    r"(?m)^[\s•\-\*]*(?:[A-Z][\w .+/&-]{2,40})\s+at\s+([A-Z][\w .&-]{1,40})\s*$"
)
_TITLE_AT = re.compile(
    r"(?m)^[\s•\-\*]*([A-Z][A-Za-z0-9 .+/&-]{2,50})\s+at\s+([A-Z][A-Za-z0-9 .&-]{1,40})\s*$"
)


def parse_resume(*, resume_text: str | None = None, skills: list[str] | None = None) -> dict:
    data = DataLoader.get()
    direct: list[str] = []
    past_roles: list[str] = []
    experience_years: int | None = None
    location: str | None = None
    contact = {"email": None, "linkedin": None, "github": None}

    if skills:
        direct = [s.strip() for s in skills if s and s.strip()]
    elif resume_text:
        req, nice = extract_skills(resume_text, data.skills)
        seen: set[str] = set()
        for s in req + nice:
            if s not in seen:
                seen.add(s)
                direct.append(s)
        contact["email"] = _first(_EMAIL, resume_text)
        contact["linkedin"] = _first(_LINKEDIN, resume_text)
        contact["github"] = _first(_GITHUB, resume_text)
        experience_years = _years(resume_text)
        location = _guess_location(resume_text, data.locations)
        past_roles = _past_roles(resume_text)
    else:
        return {
            "skills": [],
            "inferred": [],
            "past_roles": [],
            "experience_years": None,
            "location": None,
            "contact": contact,
            "market_fit": None,
        }

    profile = expand_user_skills(direct)
    inferred = [
        {
            "name": s.name,
            "confidence": s.confidence,
            "inferred_from": s.inferred_from,
            "source": s.source,
        }
        for s in profile.inferred
    ]
    return {
        "skills": direct,
        "inferred": inferred,
        "past_roles": past_roles,
        "experience_years": experience_years,
        "location": location,
        "contact": contact,
        "market_fit": None,
    }


def _first(pat: re.Pattern, text: str) -> str | None:
    m = pat.search(text or "")
    return m.group(0) if m else None


def _years(text: str) -> int | None:
    m = _YEARS.search(text or "")
    if not m:
        return None
    for g in m.groups():
        if g:
            return int(g)
    return None


def _guess_location(text: str, locations: dict) -> str | None:
    lower = (text or "").lower()
    for alias, city in (locations.get("city_aliases") or {}).items():
        if re.search(r"\b" + re.escape(alias.lower()) + r"\b", lower):
            return city
    for city in locations.get("city_default_states") or {}:
        if re.search(r"\b" + re.escape(city.lower()) + r"\b", lower):
            return city
    return None


def _past_roles(text: str) -> list[str]:
    out: list[str] = []
    for m in _TITLE_AT.finditer(text or ""):
        title, company = m.group(1).strip(), m.group(2).strip()
        label = f"{title} at {company}"
        if label not in out:
            out.append(label)
        if len(out) >= 8:
            break
    return out
