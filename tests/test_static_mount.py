"""Static UI mount — Phase 5 shell."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.web_ui import STATIC_DIR, mount_web_ui


def test_static_files_exist_on_disk():
    assert (STATIC_DIR / "index.html").is_file()
    assert (STATIC_DIR / "css" / "styles.css").is_file()
    assert (STATIC_DIR / "js" / "app.js").is_file()
    assert (STATIC_DIR / "assets" / "logo.svg").is_file()


def test_index_and_css_served():
    app = FastAPI()
    mount_web_ui(app)
    with TestClient(app) as client:
        r = client.get("/")
        assert r.status_code == 200
        assert "HireLoop" in r.text
        assert 'id="tab-browse"' in r.text
        assert 'id="mcp-setup"' in r.text
        assert "/static/js/mcp.js" in r.text
        css = client.get("/static/css/styles.css")
        assert css.status_code == 200
        assert "--blue-600" in css.text
        mcp_js = client.get("/static/js/mcp.js")
        assert mcp_js.status_code == 200
        assert "callTool" in mcp_js.text
        browse = client.get("/static/js/browse.js")
        assert browse.status_code == 200
        assert 'id="f-posted"' in browse.text
        assert "posted_within_hours" in browse.text
        matches = client.get("/static/js/matches.js")
        assert matches.status_code == 200
        assert "HireLoopMCP" in matches.text
        assert "You're done" in matches.text
        comps = client.get("/static/js/components.js")
        assert "No apply link" in comps.text
