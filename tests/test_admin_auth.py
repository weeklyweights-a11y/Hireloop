"""Admin auth dependency tests (no MCP import)."""
from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from src import deps
from src.config import settings


def test_require_admin_key_open_when_unset(monkeypatch):
    monkeypatch.setattr(settings, "admin_key", "")

    async def _run():
        await deps.require_admin_key(x_admin_key=None)

    asyncio.run(_run())


def test_require_admin_key_rejects_missing(monkeypatch):
    monkeypatch.setattr(settings, "admin_key", "secret-test-key")

    async def _run():
        with pytest.raises(HTTPException) as ei:
            await deps.require_admin_key(x_admin_key=None)
        assert ei.value.status_code == 401

    asyncio.run(_run())


def test_require_admin_key_accepts_match(monkeypatch):
    monkeypatch.setattr(settings, "admin_key", "secret-test-key")

    async def _run():
        await deps.require_admin_key(x_admin_key="secret-test-key")

    asyncio.run(_run())
