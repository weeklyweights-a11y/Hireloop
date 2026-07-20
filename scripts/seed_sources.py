"""Seed job_source_configs from src/data/sources/*.json. Idempotent by company_slug."""

import json
from pathlib import Path

from sqlalchemy import select

from src.models import JobSourceConfig, get_sync_db

SOURCES_DIR = Path(__file__).resolve().parents[1] / "src" / "data" / "sources"


def main() -> None:
    new, existing = 0, 0
    with get_sync_db() as db:
        seeded_slugs = set(db.scalars(select(JobSourceConfig.company_slug)).all())
        for path in sorted(SOURCES_DIR.glob("*.json")):
            for config in json.loads(path.read_text(encoding="utf-8")):
                if config["company_slug"] in seeded_slugs:
                    existing += 1
                    continue
                db.add(JobSourceConfig(**config))
                seeded_slugs.add(config["company_slug"])
                new += 1
    print(f"Seeded {new} new configs, {existing} already existed, {new + existing} total")


if __name__ == "__main__":
    main()
