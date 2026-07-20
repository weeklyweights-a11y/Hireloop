"""Match response detail tiers + token-ish truncation."""
from __future__ import annotations

import json
from typing import Any


def apply_detail_tier(payload: dict, detail: str = "summary") -> dict:
    detail = (detail or "summary").lower()
    matches = payload.get("matches") or []
    if detail == "scores_only":
        slim = []
        for m in matches:
            job = m.get("job") or {}
            score = m.get("score") or {}
            slim.append(
                {
                    "job": {
                        "id": job.get("id"),
                        "title": job.get("title"),
                        "company": job.get("company"),
                    },
                    "score": {"overall": score.get("overall")},
                }
            )
        payload = {**payload, "matches": slim}
        # drop heavy blocks
        payload.pop("skill_gaps", None)
        return payload

    if detail == "summary":
        slim = []
        for m in matches:
            job = m.get("job") or {}
            score = m.get("score") or {}
            analysis = m.get("skills_analysis") or {}
            matched = analysis.get("matched") or score.get("matched_skills") or []
            missing = analysis.get("missing") or score.get("missing_skills") or []
            if matched and isinstance(matched[0], dict):
                top_matched = [x.get("skill") for x in matched[:3]]
            else:
                top_matched = list(matched)[:3]
            slim.append(
                {
                    "job": {
                        "id": job.get("id"),
                        "title": job.get("title"),
                        "company": job.get("company"),
                        "location": job.get("location"),
                        "salary_range": job.get("salary_range"),
                        "apply_url": job.get("apply_url"),
                        "freshness": job.get("freshness"),
                    },
                    "score": {"overall": score.get("overall")},
                    "skills_analysis": {
                        "matched": top_matched,
                        "missing": list(missing)[:2],
                    },
                }
            )
        gaps = payload.get("skill_gaps") or []
        payload = {
            **payload,
            "matches": slim,
            "skill_gaps": gaps[:5],
        }
        return payload

    # full — keep as-is
    return payload


def maybe_truncate(payload: dict, token_budget: int = 4000) -> dict:
    raw = json.dumps(payload, default=str)
    if len(raw) / 4 <= token_budget:
        return payload

    out: dict[str, Any] = {**payload, "truncated": True}
    matches = []
    for m in out.get("matches") or []:
        job = dict(m.get("job") or {})
        if job.get("description_text"):
            job["description_text"] = str(job["description_text"])[:100]
        score = dict(m.get("score") or {})
        if "matched_skills" in score:
            score["matched_skills"] = score["matched_skills"][:5]
        if "missing_skills" in score:
            score["missing_skills"] = score["missing_skills"][:3]
        analysis = dict(m.get("skills_analysis") or {})
        if "matched" in analysis:
            analysis["matched"] = analysis["matched"][:5]
        if "missing" in analysis:
            analysis["missing"] = analysis["missing"][:3]
        matches.append({**m, "job": job, "score": score, "skills_analysis": analysis})
    out["matches"] = matches
    if "skill_gaps" in out:
        out["skill_gaps"] = (out.get("skill_gaps") or [])[:3]
    return out
