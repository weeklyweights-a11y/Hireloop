"""Admin route dependency — optional X-Admin-Key (open when ADMIN_KEY unset)."""
from __future__ import annotations

from fastapi import Header, HTTPException

from src.config import settings


async def require_admin_key(x_admin_key: str | None = Header(default=None)) -> None:
    expected = (settings.admin_key or "").strip()
    if not expected:
        return
    if x_admin_key != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")
