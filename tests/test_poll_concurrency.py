"""Tests for concurrent poll domain grouping + OSS poll summary fields."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.workers.poll_task import SLEEP_BETWEEN_SAME_DOMAIN, group_configs_by_domain


def test_group_configs_by_domain():
    configs = [
        SimpleNamespace(api_endpoint="https://boards-api.greenhouse.io/v1/boards/a/jobs"),
        SimpleNamespace(api_endpoint="https://boards-api.greenhouse.io/v1/boards/b/jobs"),
        SimpleNamespace(api_endpoint="https://api.lever.co/v0/postings/c"),
    ]
    groups = group_configs_by_domain(configs)
    assert len(groups["boards-api.greenhouse.io"]) == 2
    assert len(groups["api.lever.co"]) == 1


def test_same_domain_sleep_is_half_second():
    assert SLEEP_BETWEEN_SAME_DOMAIN == 0.5


def test_poll_summary_uses_oss_field_names():
    from src.workers import poll_task

    fake_stats = SimpleNamespace(total_active_jobs=42)
    with (
        patch.object(poll_task, "get_sync_db") as mock_db,
        patch.object(poll_task, "refresh_stats", return_value=fake_stats),
        patch.object(poll_task, "ThreadPoolExecutor") as mock_pool,
    ):
        # empty active configs → no domain work
        session = MagicMock()
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)
        session.scalars.return_value.all.return_value = []
        mock_db.return_value = session

        class _Immediate:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def submit(self, fn, *args):
                fut = MagicMock()
                fut.result.return_value = []
                return fut

        mock_pool.return_value = _Immediate()
        # as_completed over empty — patch to return []
        with patch.object(poll_task, "as_completed", return_value=[]):
            summary = poll_task.poll_all_sources()

    assert summary["event"] == "poll_cycle_complete"
    assert "succeeded" in summary
    assert "failed" in summary
    assert "duration_seconds" in summary
    assert "total_active" in summary
    assert summary["total_active"] == 42
    assert "duration_minutes" not in summary
    assert "sources_succeeded" not in summary
