from __future__ import annotations

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from src.models import Job

ATS_RANK: dict[str, int] = {
    "custom": 5,
    "greenhouse": 4,
    "lever": 3,
    "workday": 2,
    "ashby": 1,
}


def _rank(ats: str | None) -> int:
    return ATS_RANK.get((ats or "").lower(), 0)


def _both_remote(a: Job, b: Job) -> bool:
    return (a.remote_policy or "") == "remote" and (b.remote_policy or "") == "remote"


def _same_city(a: Job, b: Job) -> bool:
    if not a.location_city or not b.location_city:
        return False
    return a.location_city.lower() == b.location_city.lower()


def check_duplicate(new_job: Job, db: Session) -> Job | None:
    """If a cross-source duplicate exists, mark the lower-ranked row duplicate.

    Equal ATS rank: keep the existing (already-in-DB) row active; mark new as duplicate.
    Returns the row that remains active (the keeper), or None if no duplicate.
    """
    if new_job.status != "active":
        return None

    candidates = (
        db.query(Job)
        .filter(
            Job.status == "active",
            Job.id != new_job.id,
            Job.company_name.ilike(new_job.company_name),
            # Cross-source only — same board re-poll must not O(n²) against itself
            Job.source_company_slug != new_job.source_company_slug,
        )
        .all()
    )

    for existing in candidates:
        if fuzz.token_set_ratio(new_job.title_raw or "", existing.title_raw or "") <= 90:
            continue
        if not (_same_city(new_job, existing) or _both_remote(new_job, existing)):
            continue

        new_rank = _rank(new_job.source_ats)
        old_rank = _rank(existing.source_ats)

        if new_rank > old_rank:
            existing.status = "duplicate"
            return new_job
        # Equal or lower: keep existing, mark new duplicate
        new_job.status = "duplicate"
        return existing

    return None
