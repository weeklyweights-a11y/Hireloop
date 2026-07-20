"""User skill expansion via Neo4j IMPLIES (outgoing / lateral)."""
from __future__ import annotations

from src.graph.connection import is_available, sync_session
from src.schemas.matching import ExpandedSkillProfile, SkillWithConfidence
from src.services.data_loader import DataLoader
from src.services.job_service import _resolve_skill_canonical

_ONE_HOP = """
MATCH (stated:Skill {name: $skill})-[rel:IMPLIES]->(parent:Skill)
WHERE rel.strength >= 80
RETURN parent.name AS skill, rel.strength AS strength
"""

_TWO_HOP = """
MATCH (stated:Skill {name: $skill})-[:IMPLIES]->()-[:IMPLIES]->(grandparent:Skill)
WHERE NOT grandparent.name IN $already_found
RETURN DISTINCT grandparent.name AS skill
"""

_LATERAL = """
MATCH (stated:Skill {name: $skill})-[r:IMPLIES]-(related:Skill)
WHERE r.strength >= 60 AND r.strength < 80
  AND NOT related.name IN $already_found
RETURN related.name AS skill, r.strength AS strength
"""


def _canonical(name: str) -> str:
    return _resolve_skill_canonical(name, DataLoader.get())


def _run_cypher(cypher: str, **params) -> list[dict]:
    """Overridable in tests. Returns list of record dicts."""
    with sync_session() as session:
        return [dict(r) for r in session.run(cypher, **params)]


def _best(
    bucket: dict[str, SkillWithConfidence], item: SkillWithConfidence
) -> None:
    prev = bucket.get(item.name)
    if prev is None or item.confidence > prev.confidence:
        bucket[item.name] = item


def _row_confidence(row: dict, *, mode: str) -> float:
    """Prefer injected test confidence; else derive from strength."""
    if "confidence" in row and "strength" not in row:
        return float(row["confidence"])
    if mode == "one_hop":
        return float(row.get("strength") or 0) * 0.9 / 100.0
    if mode == "two_hop":
        return float(row.get("confidence", 0.7))
    if mode == "lateral":
        if "confidence" in row and "strength" not in row:
            return float(row["confidence"])
        return float(row.get("strength") or 0) * 0.005
    return 0.0


def expand_user_skills(skills: list[str]) -> ExpandedSkillProfile:
    if not skills:
        return ExpandedSkillProfile()

    direct: dict[str, SkillWithConfidence] = {}
    for raw in skills:
        name = _canonical(raw)
        if not name:
            continue
        direct[name] = SkillWithConfidence(
            name=name, confidence=1.0, source="direct", inferred_from=None
        )

    inferred: dict[str, SkillWithConfidence] = {}
    lateral: dict[str, SkillWithConfidence] = {}

    if not is_available():
        all_skills = sorted(direct.values(), key=lambda s: (-s.confidence, s.name))
        return ExpandedSkillProfile(
            direct=list(direct.values()),
            inferred=[],
            lateral=[],
            all_skills=all_skills,
        )

    found = set(direct.keys())

    for skill in list(direct.keys()):
        try:
            rows = _run_cypher(_ONE_HOP, skill=skill)
        except Exception:
            rows = []
        for row in rows:
            parent = row["skill"]
            if parent in direct:
                continue
            conf = _row_confidence(row, mode="one_hop")
            _best(
                inferred,
                SkillWithConfidence(
                    name=parent,
                    confidence=conf,
                    source="inferred",
                    inferred_from=skill,
                ),
            )
            found.add(parent)

    for skill in list(direct.keys()):
        try:
            rows = _run_cypher(_TWO_HOP, skill=skill, already_found=list(found))
        except Exception:
            rows = []
        for row in rows:
            name = row["skill"]
            if name in direct:
                continue
            conf = _row_confidence(row, mode="two_hop")
            _best(
                inferred,
                SkillWithConfidence(
                    name=name,
                    confidence=conf,
                    source="inferred",
                    inferred_from=skill,
                ),
            )
            found.add(name)

    for skill in list(direct.keys()):
        try:
            rows = _run_cypher(_LATERAL, skill=skill, already_found=list(found))
        except Exception:
            rows = []
        for row in rows:
            name = row["skill"]
            if name in direct or name in inferred:
                continue
            conf = _row_confidence(row, mode="lateral")
            _best(
                lateral,
                SkillWithConfidence(
                    name=name,
                    confidence=conf,
                    source="lateral",
                    inferred_from=skill,
                ),
            )

    all_skills = sorted(
        [*direct.values(), *inferred.values(), *lateral.values()],
        key=lambda s: (-s.confidence, s.name),
    )
    return ExpandedSkillProfile(
        direct=list(direct.values()),
        inferred=list(inferred.values()),
        lateral=list(lateral.values()),
        all_skills=all_skills,
    )
