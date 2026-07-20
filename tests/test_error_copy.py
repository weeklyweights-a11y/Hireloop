"""Empty-result and error copy smoke."""

from src.errors import (
    CompanyNotFoundError,
    GraphUnavailableError,
    JobNotFoundError,
    RateLimitError,
)
from src.mcp.tools import NO_RESULTS_MESSAGE


def test_error_copy_mentions_recovery():
    assert "career page" in JobNotFoundError().detail.lower()
    assert "100" in RateLimitError().detail
    assert "search" in GraphUnavailableError().detail.lower()
    assert "list_companies" in CompanyNotFoundError().detail


def test_no_results_message():
    assert "No jobs matched" in NO_RESULTS_MESSAGE
