"""Source admin CRUD helpers — schema + list filter smoke."""
from __future__ import annotations

import inspect

from src.routers import admin
from src.routers.admin import SourceCreate, SourceUpdate


def test_source_create_schema():
    body = SourceCreate(
        company_name="Acme",
        company_slug="acme",
        ats_type="greenhouse",
        api_endpoint="https://boards-api.greenhouse.io/v1/boards/acme/jobs",
        field_mapping={"id": "id", "title": "title"},
    )
    assert body.company_slug == "acme"
    assert body.active is True


def test_source_update_partial():
    body = SourceUpdate(active=False)
    assert body.model_dump(exclude_unset=True) == {"active": False}


def test_list_sources_accepts_active_filter():
    sig = inspect.signature(admin.list_sources)
    assert "active" in sig.parameters
    assert sig.parameters["active"].default == "all"


def test_toggle_and_rebuild_routes_exist():
    paths = {getattr(r, "path", None) for r in admin.router.routes}
    assert "/admin/sources/{source_id}/toggle" in paths
    assert "/admin/graph/rebuild" in paths
