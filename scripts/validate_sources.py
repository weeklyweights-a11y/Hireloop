"""Validate each active source config by calling its API. Hard failures get active=false."""

import asyncio

import httpx
from sqlalchemy import select

from src.models import JobSourceConfig, get_sync_db
from src.services.field_mapper import get_path

CONCURRENCY = 10
TIMEOUT = 20.0


def extract_jobs(payload, response_path: str | None):
    data = get_path(payload, response_path) if response_path else payload
    return data if isinstance(data, list) else None


async def check(client: httpx.AsyncClient, cfg: dict) -> tuple[str, int, str | None]:
    """Return (slug, job_count, error). error=None means pass."""
    try:
        resp = await client.request(
            cfg["api_method"],
            cfg["api_endpoint"],
            headers=cfg["api_headers"] or None,
            params=cfg["api_params"] or None,
            json=cfg["api_body"],
        )
    except httpx.HTTPError as e:
        return cfg["company_slug"], 0, f"{type(e).__name__}: {e}"
    if resp.status_code != 200:
        return cfg["company_slug"], 0, f"HTTP {resp.status_code}"
    try:
        payload = resp.json()
    except ValueError:
        return cfg["company_slug"], 0, "invalid JSON"
    jobs = extract_jobs(payload, cfg["response_path"])
    if jobs is None:
        return cfg["company_slug"], 0, f"no job array at response_path={cfg['response_path']!r}"
    title_path = (cfg["field_mapping"] or {}).get("title")
    if not title_path:
        return cfg["company_slug"], 0, "field_mapping has no title path"
    if jobs and get_path(jobs[0], title_path) is None:
        return cfg["company_slug"], 0, f"title path {title_path!r} not found in first job"
    return cfg["company_slug"], len(jobs), None


async def run(configs: list[dict]) -> list[tuple[str, int, str | None]]:
    sem = asyncio.Semaphore(CONCURRENCY)
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:

        async def bounded(cfg):
            async with sem:
                return await check(client, cfg)

        return await asyncio.gather(*(bounded(c) for c in configs))


def main() -> None:
    with get_sync_db() as db:
        rows = db.scalars(select(JobSourceConfig).where(JobSourceConfig.active)).all()
        configs = [
            {
                "company_slug": r.company_slug,
                "company_name": r.company_name,
                "ats_type": r.ats_type,
                "api_endpoint": r.api_endpoint,
                "api_method": r.api_method,
                "api_headers": r.api_headers,
                "api_params": r.api_params,
                "api_body": r.api_body,
                "response_path": r.response_path,
                "field_mapping": r.field_mapping,
            }
            for r in rows
        ]

    results = asyncio.run(run(configs))
    by_slug = {c["company_slug"]: c for c in configs}

    passed = failed = 0
    failures: list[tuple[str, str]] = []
    for slug, count, error in results:
        c = by_slug[slug]
        if error is None:
            passed += 1
            print(f"[ok]   {c['company_name']} ({c['ats_type']}): {count} jobs")
        else:
            failed += 1
            failures.append((slug, error))
            print(f"[FAIL] {c['company_name']} ({c['ats_type']}): {error}")

    if failures:
        with get_sync_db() as db:
            for slug, error in failures:
                cfg = db.scalars(
                    select(JobSourceConfig).where(JobSourceConfig.company_slug == slug)
                ).one()
                cfg.active = False
                cfg.last_error = f"validation: {error}"

    print(f"\n{passed} passed, {failed} failed, {passed + failed} total")


if __name__ == "__main__":
    main()
