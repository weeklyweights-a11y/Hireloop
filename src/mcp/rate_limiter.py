from __future__ import annotations

import time

import redis

from src.config import settings
from src.errors import RateLimitError


class RateLimiter:
    """Redis sliding-window rate limiter keyed by client IP."""

    def __init__(
        self,
        redis_url: str | None = None,
        limit: int | None = None,
        window_seconds: int = 3600,
    ) -> None:
        self.limit = limit if limit is not None else settings.rate_limit_per_hour
        self.window = window_seconds
        self._redis = redis.from_url(redis_url or settings.redis_url, decode_responses=True)

    def check(self, client_ip: str) -> None:
        """Raise RateLimitError if this IP has exceeded the hourly budget."""
        key = f"hireloop:mcp:rl:{client_ip}"
        now = time.time()
        window_start = now - self.window
        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        _, count = pipe.execute()
        if count >= self.limit:
            retry_mins = max(1, int(self.window / 60))
            raise RateLimitError(
                f"Rate limit exceeded. {self.limit} requests per hour. "
                f"Try again in {retry_mins} minutes."
            )
        pipe = self._redis.pipeline()
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, self.window)
        pipe.execute()


def client_ip_from_headers(headers: dict[str, str], fallback: str = "127.0.0.1") -> str:
    forwarded = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return headers.get("x-real-ip") or headers.get("X-Real-IP") or fallback
