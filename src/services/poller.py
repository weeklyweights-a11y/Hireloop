import time
from datetime import UTC, datetime

import httpx
import structlog
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models import Job, JobSourceConfig, PollLog
from src.services.differ import apply_diff, diff_jobs
from src.services.field_mapper import extract_jobs_array, map_fields

logger = structlog.get_logger()

MAX_PAGES = 100
MAX_JOBS_PER_POLL = 5000
TIMEOUT_SECONDS = 30.0


class PollResult(BaseModel):
    company_name: str
    status: str  # success | rate_limited | client_error | server_error | timeout | connection_error | invalid_json | bot_detection
    jobs_found: int = 0
    jobs_new: int = 0
    jobs_updated: int = 0
    jobs_closed: int = 0
    duration_ms: int = 0
    error: str | None = None


class _PollFailure(Exception):
    def __init__(self, status: str, error: str) -> None:
        self.status = status
        self.error = error
        super().__init__(error)


def _looks_like_html(response: httpx.Response) -> bool:
    if "text/html" in response.headers.get("content-type", ""):
        return True
    body_start = response.text[:100].lstrip().lower()
    return body_start.startswith(("<!doctype", "<html"))


def _fetch_page(client: httpx.Client, config: JobSourceConfig, params: dict) -> list[dict]:
    """One HTTP request -> raw jobs array. Raises _PollFailure on any error."""
    try:
        response = client.request(
            config.api_method or "GET",
            config.api_endpoint,
            headers={"User-Agent": "HireLoop/1.0", **(config.api_headers or {})},
            params=params or None,
            json=config.api_body,
        )
    except httpx.TimeoutException as e:
        raise _PollFailure("timeout", f"timeout after {TIMEOUT_SECONDS}s: {e}") from e
    except httpx.HTTPError as e:
        raise _PollFailure("connection_error", f"{type(e).__name__}: {e}") from e

    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After")
        wait_s = 5.0
        if retry_after:
            try:
                wait_s = float(retry_after)
            except ValueError:
                wait_s = 5.0
        time.sleep(min(wait_s, 60.0))
        try:
            response = client.request(
                config.api_method or "GET",
                config.api_endpoint,
                headers={"User-Agent": "HireLoop/1.0", **(config.api_headers or {})},
                params=params or None,
                json=config.api_body,
            )
        except httpx.HTTPError as e:
            raise _PollFailure("connection_error", f"retry after 429 failed: {e}") from e
        if response.status_code == 429:
            raise _PollFailure("rate_limited", "HTTP 429 after retry")
    if 400 <= response.status_code < 500:
        raise _PollFailure("client_error", f"HTTP {response.status_code}")
    if response.status_code >= 500:
        raise _PollFailure("server_error", f"HTTP {response.status_code}")

    if _looks_like_html(response):
        # CAPTCHA / bot wall — retrying won't clear it this cycle
        raise _PollFailure("bot_detection", "got HTML instead of JSON (CAPTCHA/bot wall?)")

    try:
        payload = response.json()
    except ValueError as e:
        raise _PollFailure("invalid_json", f"JSON decode failed: {e}") from e

    return extract_jobs_array(payload, config.response_path)


def _fetch_all_jobs(config: JobSourceConfig, transport: httpx.BaseTransport | None) -> list:
    """Fetch every page (respecting hard caps), returning mapped jobs."""
    pagination = config.pagination_config or {}
    ptype = pagination.get("type", "none")
    mapped_jobs = []

    def consume(raw_jobs: list[dict]) -> int:
        added = 0
        for raw in raw_jobs:
            job = map_fields(raw, config.field_mapping)
            if job is not None:
                mapped_jobs.append(job)
                added += 1
            if len(mapped_jobs) >= MAX_JOBS_PER_POLL:
                break
        return added

    with httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=True, transport=transport) as client:
        base_params = dict(config.api_params or {})

        if ptype == "page":
            param = pagination["param"]
            page = 1
            while page <= MAX_PAGES and len(mapped_jobs) < MAX_JOBS_PER_POLL:
                raw = _fetch_page(client, config, {**base_params, param: str(page)})
                if not raw:
                    break
                consume(raw)
                page += 1
        elif ptype == "offset":
            param = pagination["param"]
            limit = int(pagination.get("limit", 100))
            offset = 0
            while offset <= MAX_JOBS_PER_POLL and len(mapped_jobs) < MAX_JOBS_PER_POLL:
                raw = _fetch_page(client, config, {**base_params, param: str(offset)})
                if not raw:
                    break
                consume(raw)
                offset += limit
        else:
            consume(_fetch_page(client, config, base_params))

    return mapped_jobs


def poll_source(
    config: JobSourceConfig,
    db_session: Session,
    transport: httpx.BaseTransport | None = None,
) -> PollResult:
    logger.info("polling", company=config.company_name, ats=config.ats_type)
    start = time.monotonic()
    now = datetime.now(UTC)

    try:
        api_jobs = _fetch_all_jobs(config, transport)
    except _PollFailure as failure:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.warning(
            "poll_failed", company=config.company_name, status=failure.status, error=failure.error
        )
        config.last_polled_at = now
        config.last_error = failure.error
        db_session.add(
            PollLog(
                source_config_id=config.id,
                company_name=config.company_name,
                status=failure.status,
                duration_ms=duration_ms,
                error_message=failure.error,
            )
        )
        return PollResult(
            company_name=config.company_name,
            status=failure.status,
            duration_ms=duration_ms,
            error=failure.error,
        )

    # active AND closed rows: needed for miss reset, reappearance, and the unique constraint
    db_jobs = list(
        db_session.scalars(
            select(Job).where(Job.source_company_slug == config.company_slug)
        ).all()
    )
    diff = diff_jobs(config.company_slug, config.ats_type, api_jobs, db_jobs)
    applied = apply_diff(diff, config, db_session)
    db_session.flush()

    duration_ms = int((time.monotonic() - start) * 1000)
    active_count = db_session.scalar(
        select(func.count())
        .select_from(Job)
        .where(Job.source_company_slug == config.company_slug, Job.status == "active")
    )

    config.last_polled_at = now
    config.last_success_at = now
    config.last_error = None
    config.total_jobs_found = active_count

    db_session.add(
        PollLog(
            source_config_id=config.id,
            company_name=config.company_name,
            status="success",
            jobs_found=len(api_jobs),
            jobs_new=applied.jobs_inserted,
            jobs_updated=applied.jobs_updated,
            jobs_closed=applied.jobs_closed,
            duration_ms=duration_ms,
        )
    )
    logger.info(
        "poll_success",
        company=config.company_name,
        found=len(api_jobs),
        new=applied.jobs_inserted,
        updated=applied.jobs_updated,
        closed=applied.jobs_closed,
    )
    return PollResult(
        company_name=config.company_name,
        status="success",
        jobs_found=len(api_jobs),
        jobs_new=applied.jobs_inserted,
        jobs_updated=applied.jobs_updated,
        jobs_closed=applied.jobs_closed,
        duration_ms=duration_ms,
    )
