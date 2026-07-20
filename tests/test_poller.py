import json

import httpx
import pytest

from src.models import JobSourceConfig, PollLog
from src.services.poller import MAX_JOBS_PER_POLL, poll_source

FIELD_MAPPING = {"id": "id", "title": "title", "description": "content"}


@pytest.fixture
def config(db_session):
    cfg = JobSourceConfig(
        company_name="Poller Test Co",
        company_slug="poller-test-co",
        ats_type="greenhouse",
        api_endpoint="https://example.test/jobs",
        api_method="GET",
        api_headers={},
        api_params={},
        response_path="jobs",
        field_mapping=FIELD_MAPPING,
        pagination_config={"type": "none"},
    )
    db_session.add(cfg)
    db_session.flush()
    return cfg


def transport_returning(handler):
    return httpx.MockTransport(handler)


def json_response(payload, status=200):
    return httpx.Response(
        status, content=json.dumps(payload), headers={"content-type": "application/json"}
    )


def jobs_payload(n, start=0):
    return {"jobs": [{"id": start + i, "title": f"Job {start + i}", "content": "x"} for i in range(n)]}


def test_successful_poll(config, db_session):
    transport = transport_returning(lambda req: json_response(jobs_payload(3)))
    result = poll_source(config, db_session, transport=transport)
    assert result.status == "success"
    assert result.jobs_found == 3
    assert result.jobs_new == 3
    assert result.jobs_closed == 0


def test_http_429_rate_limited(config, db_session):
    transport = transport_returning(lambda req: httpx.Response(429))
    result = poll_source(config, db_session, transport=transport)
    assert result.status == "rate_limited"


def test_http_500_server_error(config, db_session):
    transport = transport_returning(lambda req: httpx.Response(500))
    result = poll_source(config, db_session, transport=transport)
    assert result.status == "server_error"


def test_timeout(config, db_session):
    def handler(req):
        raise httpx.ConnectTimeout("too slow")

    result = poll_source(config, db_session, transport=transport_returning(handler))
    assert result.status == "timeout"


def test_invalid_json(config, db_session):
    transport = transport_returning(
        lambda req: httpx.Response(
            200, content="{not json", headers={"content-type": "application/json"}
        )
    )
    result = poll_source(config, db_session, transport=transport)
    assert result.status == "invalid_json"


def test_html_response_is_bot_detection(config, db_session):
    transport = transport_returning(
        lambda req: httpx.Response(
            200,
            content="<!DOCTYPE html><html>captcha</html>",
            headers={"content-type": "text/html"},
        )
    )
    result = poll_source(config, db_session, transport=transport)
    assert result.status == "bot_detection"
    assert config.last_error is not None
    assert "HTML" in config.last_error


def test_paginated_source_fetches_all_pages(config, db_session):
    config.pagination_config = {"type": "page", "param": "page"}
    pages = {1: jobs_payload(2, 0), 2: jobs_payload(2, 2), 3: {"jobs": []}}

    def handler(req):
        page = int(req.url.params["page"])
        return json_response(pages[page])

    result = poll_source(config, db_session, transport=transport_returning(handler))
    assert result.status == "success"
    assert result.jobs_found == 4


def test_pagination_stops_at_safety_limit(config, db_session):
    config.pagination_config = {"type": "page", "param": "page"}
    calls = []

    def handler(req):
        page = int(req.url.params["page"])
        calls.append(page)
        return json_response(jobs_payload(100, start=page * 1000))  # never empty

    result = poll_source(config, db_session, transport=transport_returning(handler))
    assert result.status == "success"
    assert result.jobs_found == MAX_JOBS_PER_POLL
    assert max(calls) <= 100


def test_poll_log_created(config, db_session):
    transport = transport_returning(lambda req: json_response(jobs_payload(1)))
    poll_source(config, db_session, transport=transport)
    db_session.flush()
    logs = db_session.query(PollLog).filter(PollLog.source_config_id == config.id).all()
    assert len(logs) == 1
    assert logs[0].status == "success"
    assert logs[0].jobs_new == 1


def test_source_config_updated_after_success(config, db_session):
    transport = transport_returning(lambda req: json_response(jobs_payload(2)))
    poll_source(config, db_session, transport=transport)
    assert config.last_polled_at is not None
    assert config.last_success_at is not None
    assert config.last_error is None
    assert config.total_jobs_found == 2


def test_source_config_error_set_after_failure(config, db_session):
    transport = transport_returning(lambda req: httpx.Response(500))
    poll_source(config, db_session, transport=transport)
    assert config.last_error == "HTTP 500"
    assert config.last_success_at is None


def test_jobs_missing_id_or_title_skipped(config, db_session):
    payload = {"jobs": [{"id": 1, "title": "Good"}, {"title": "No id"}, {"id": 3}]}
    transport = transport_returning(lambda req: json_response(payload))
    result = poll_source(config, db_session, transport=transport)
    assert result.jobs_found == 1
