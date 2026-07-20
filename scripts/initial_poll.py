"""First full poll cycle, synchronous — watch live progress and fix issues early."""

import time
from datetime import UTC, datetime

from sqlalchemy import select

from src.models import JobSourceConfig, get_sync_db
from src.services.poller import poll_source
from src.workers.stats_task import refresh_stats


def main() -> None:
    with get_sync_db() as db:
        config_ids = db.scalars(select(JobSourceConfig.id).where(JobSourceConfig.active)).all()
    total = len(config_ids)
    print(f"Polling {total} active sources...\n")

    started = time.monotonic()
    succeeded = failed = new = updated = closed = 0
    for i, config_id in enumerate(config_ids, 1):
        try:
            with get_sync_db() as db:
                config = db.get(JobSourceConfig, config_id)
                result = poll_source(config, db)
        except Exception as e:
            failed += 1
            print(f"[{i}/{total}] CRASH {type(e).__name__}: {e}")
            continue

        if result.status == "success":
            succeeded += 1
            new += result.jobs_new
            updated += result.jobs_updated
            closed += result.jobs_closed
            print(
                f"[{i}/{total}] {result.company_name}: {result.jobs_found} jobs "
                f"(+{result.jobs_new}) | running total: {new} new, {closed} closed"
            )
        else:
            failed += 1
            print(f"[{i}/{total}] {result.company_name}: {result.status} — {result.error}")
        time.sleep(0.5)

    with get_sync_db() as db:
        refresh_stats(db, last_full_poll_at=datetime.now(UTC))

    minutes = (time.monotonic() - started) / 60
    print(
        f"\nDone in {minutes:.1f} min: {succeeded} succeeded, {failed} failed, "
        f"{new} new jobs, {updated} updated, {closed} closed"
    )


if __name__ == "__main__":
    main()
