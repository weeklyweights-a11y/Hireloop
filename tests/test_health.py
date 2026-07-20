"""Health payload shape tests (probes may be unavailable in CI)."""

from src.services.health import build_health_payload


def test_health_payload_has_oss_fields():
    payload = build_health_payload()
    assert "status" in payload
    assert "version" in payload
    assert "uptime_seconds" in payload
    assert "setup" in payload
    assert {"sources_configured", "first_poll_complete", "jobs_loaded", "message"} <= set(
        payload["setup"]
    )
    assert "databases" in payload
    assert {"postgres", "redis", "neo4j"} <= set(payload["databases"])
    assert "data" in payload
    data = payload["data"]
    for key in (
        "total_active_jobs",
        "total_companies",
        "total_sources_active",
        "sources_with_errors",
        "last_poll",
        "last_poll_age_minutes",
        "next_poll",
        "graph_last_built",
    ):
        assert key in data
    assert isinstance(payload["warnings"], list)
