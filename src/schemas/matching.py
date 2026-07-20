"""Match / skill-expansion Pydantic models."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from src.schemas.jobs import JobSummary


def clamp_match_limit(limit: int | None, default: int = 20) -> int:
    n = default if limit is None else int(limit)
    return max(1, min(50, n))


class SkillWithConfidence(BaseModel):
    name: str
    confidence: float
    source: str  # direct | inferred | lateral
    inferred_from: str | None = None


class ExpandedSkillProfile(BaseModel):
    direct: list[SkillWithConfidence] = Field(default_factory=list)
    inferred: list[SkillWithConfidence] = Field(default_factory=list)
    lateral: list[SkillWithConfidence] = Field(default_factory=list)
    all_skills: list[SkillWithConfidence] = Field(default_factory=list)


class MatchFilters(BaseModel):
    target_role: str | None = None
    location: str | None = None
    remote_ok: bool = True
    salary_min: int | None = None
    experience_years: int | None = None
    visa_needed: bool = False
    seniority: str | None = None
    companies: list[str] | None = None
    posted_within_hours: int | None = None
    limit: int = 20
    offset: int = 0

    @field_validator("limit")
    @classmethod
    def _clamp_limit(cls, v: int) -> int:
        return clamp_match_limit(v)

    @field_validator("offset")
    @classmethod
    def _clamp_offset(cls, v: int) -> int:
        return max(0, int(v))


class SkillMatch(BaseModel):
    skill: str
    match_type: str
    confidence: float
    inferred_from: str | None = None


class MatchScore(BaseModel):
    overall: int
    skills_fit: int
    role_fit: int
    preference_fit: int
    freshness: int
    matched_skills: list[SkillMatch] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    inferred_skills_used: list[str] = Field(default_factory=list)
    explanation: dict = Field(default_factory=dict)


class SkillGap(BaseModel):
    skill: str
    frequency: float
    importance: str = "common"
    roles_needing: list[str] = Field(default_factory=list)
    learn_path: list[str] | None = None
    missing_in: str | None = None


class JobMatch(BaseModel):
    job: JobSummary
    score: MatchScore
    skills_analysis: dict | None = None


class MatchResult(BaseModel):
    total_matches: int
    showing: int = 0
    matches: list[JobMatch] = Field(default_factory=list)
    skill_gaps: list[SkillGap] = Field(default_factory=list)
    profile_summary: dict = Field(default_factory=dict)
    data_freshness: str = "unknown"
    truncated: bool = False
    message: str | None = None
