"""Tests for first-run setup status helpers."""

from src.services.setup_status import FIRST_POLL_MESSAGE, get_setup_status


def test_get_setup_status_shape():
    setup = get_setup_status()
    assert "sources_configured" in setup
    assert "first_poll_complete" in setup
    assert "jobs_loaded" in setup
    assert "message" in setup
    assert isinstance(setup["sources_configured"], int)
    assert isinstance(setup["jobs_loaded"], int)
    assert isinstance(setup["first_poll_complete"], bool)


def test_first_poll_message_constant():
    assert "first time" in FIRST_POLL_MESSAGE.lower()
