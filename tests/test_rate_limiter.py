from unittest.mock import MagicMock

import pytest

from src.errors import RateLimitError
from src.mcp.rate_limiter import RateLimiter, client_ip_from_headers


def test_client_ip_from_x_forwarded_for():
    assert (
        client_ip_from_headers({"X-Forwarded-For": "203.0.113.1, 10.0.0.1"})
        == "203.0.113.1"
    )


def test_client_ip_fallback():
    assert client_ip_from_headers({}, fallback="9.9.9.9") == "9.9.9.9"


def test_rate_limiter_allows_under_limit():
    fake = MagicMock()
    pipe = MagicMock()
    # first pipeline: zremrangebyscore + zcard → count=5
    pipe.execute.side_effect = [[0, 5], [True, True]]
    fake.pipeline.return_value = pipe

    limiter = RateLimiter.__new__(RateLimiter)
    limiter.limit = 100
    limiter.window = 3600
    limiter._redis = fake
    limiter.check("1.2.3.4")  # should not raise


def test_rate_limiter_blocks_at_limit():
    fake = MagicMock()
    pipe = MagicMock()
    pipe.execute.return_value = [0, 100]  # count=100 >= limit
    fake.pipeline.return_value = pipe

    limiter = RateLimiter.__new__(RateLimiter)
    limiter.limit = 100
    limiter.window = 3600
    limiter._redis = fake
    with pytest.raises(RateLimitError) as exc:
        limiter.check("1.2.3.4")
    assert exc.value.status_code == 429
    assert exc.value.error_code == "RATE_LIMIT_EXCEEDED"
