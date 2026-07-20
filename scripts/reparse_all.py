"""Re-parse all active jobs with the full Phase 2 parser (no dedup)."""

from __future__ import annotations

from sqlalchemy import func, select

from src.models import Job, get_sync_db
from src.services.data_loader import DataLoader
from src.services.parser import parse_job

BATCH = 500


def _location_input(job: Job) -> str | None:
    parts = [x for x in (job.location_city, job.location_state) if x]
    return ", ".join(parts) if parts else None


def _description_input(job: Job) -> str | None:
    return job.description_html or job.description_text


def main() -> None:
    DataLoader.get()  # warm singleton once
    with get_sync_db() as db:
        total = (
            db.scalar(select(func.count()).select_from(Job).where(Job.status == "active"))
            or 0
        )
    print(f"Re-parsing {total} active jobs...\n", flush=True)

    last_id = None
    done = 0
    titles = skills = seniority = salary = non_us = 0

    while True:
        with get_sync_db() as db:
            q = select(Job).where(Job.status == "active").order_by(Job.id).limit(BATCH)
            if last_id is not None:
                q = q.where(Job.id > last_id)
            jobs = db.scalars(q).all()
            if not jobs:
                break

            for job in jobs:
                parsed = parse_job(
                    job.title_raw,
                    _location_input(job),
                    _description_input(job),
                )
                job.title_normalized = parsed.title_normalized
                job.title_metadata = parsed.title_metadata
                if not job.department and parsed.title_department:
                    job.department = parsed.title_department
                job.seniority = parsed.seniority
                job.employment_type = parsed.employment_type
                job.visa_sponsorship = parsed.visa_sponsorship
                job.skills_required = parsed.skills_required
                job.skills_nice_to_have = parsed.skills_nice_to_have
                job.location_city = parsed.location_city
                job.location_state = parsed.location_state
                job.location_country = parsed.location_country
                job.location_metro = parsed.location_metro
                job.salary_min = parsed.salary_min
                job.salary_max = parsed.salary_max
                job.experience_min = parsed.experience_min
                job.experience_max = parsed.experience_max
                if parsed.remote_policy != "unknown":
                    job.remote_policy = parsed.remote_policy
                if job.description_html:
                    job.description_text = parsed.description_text

                done += 1
                if parsed.title_normalized:
                    titles += 1
                if parsed.skills_required or parsed.skills_nice_to_have:
                    skills += 1
                if parsed.seniority:
                    seniority += 1
                if parsed.salary_min is not None:
                    salary += 1
                if (parsed.location_country or "US") != "US":
                    non_us += 1

            last_id = jobs[-1].id
            print(f"Re-parsed {done}/{total} jobs...", flush=True)

    def pct(n: int) -> str:
        return f"{100 * n / done:.0f}%" if done else "0%"

    print(
        f"\n{done} jobs re-parsed. "
        f"{titles} titles normalized ({pct(titles)}). "
        f"{skills} with skills ({pct(skills)}). "
        f"{seniority} with seniority ({pct(seniority)}). "
        f"{salary} with salary ({pct(salary)}). "
        f"{non_us} non-US country.",
        flush=True,
    )


if __name__ == "__main__":
    main()
