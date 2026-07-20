"""Validate a single source by company_slug (does not deactivate others)."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from scripts.validate_sources import check
from src.models import JobSourceConfig, get_sync_db

SOURCES_DIR = Path(__file__).resolve().parents[1] / "src" / "data" / "sources"


def _row_to_cfg(row: JobSourceConfig) -> dict:
    return {
        "company_slug": row.company_slug,
        "company_name": row.company_name,
        "ats_type": row.ats_type,
        "api_endpoint": row.api_endpoint,
        "api_method": row.api_method,
        "api_headers": row.api_headers,
        "api_params": row.api_params,
        "api_body": row.api_body,
        "response_path": row.response_path,
        "field_mapping": row.field_mapping,
    }


def _load_from_json(slug: str) -> dict | None:
    for path in sorted(SOURCES_DIR.glob("*.json")):
        for config in json.loads(path.read_text(encoding="utf-8")):
            if config.get("company_slug") == slug:
                return {
                    "company_slug": config["company_slug"],
                    "company_name": config.get("company_name", slug),
                    "ats_type": config.get("ats_type", ""),
                    "api_endpoint": config["api_endpoint"],
                    "api_method": config.get("api_method", "GET"),
                    "api_headers": config.get("api_headers") or {},
                    "api_params": config.get("api_params") or {},
                    "api_body": config.get("api_body"),
                    "response_path": config.get("response_path"),
                    "field_mapping": config.get("field_mapping") or {},
                }
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate one HireLoop source config")
    parser.add_argument("--slug", required=True, help="company_slug to validate")
    args = parser.parse_args()
    slug = args.slug.strip()

    cfg = None
    try:
        with get_sync_db() as db:
            row = db.scalars(
                select(JobSourceConfig).where(JobSourceConfig.company_slug == slug)
            ).first()
            if row is not None:
                cfg = _row_to_cfg(row)
    except Exception:
        cfg = None

    if cfg is None:
        cfg = _load_from_json(slug)
    if cfg is None:
        raise SystemExit(f"No source found for slug={slug!r}")

    async def _run():
        import httpx

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            return await check(client, cfg)

    slug_out, count, error = asyncio.run(_run())
    if error is None:
        print(f"[ok]   {cfg['company_name']} ({cfg['ats_type']}): {count} jobs")
        raise SystemExit(0)
    print(f"[FAIL] {cfg['company_name']} ({cfg['ats_type']}): {error}")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
