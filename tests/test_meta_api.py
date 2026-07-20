"""Meta suggest endpoints for the web UI."""

from src.services.meta import suggest_locations, suggest_roles


def test_locations_remote_first():
    out = suggest_locations("")
    assert out[0] == "Remote"
    assert "San Francisco" in out or "NYC" in out or len(out) > 1


def test_locations_filter():
    out = suggest_locations("san fran")
    assert out[0] == "Remote"
    assert any("francisco" in x.lower() for x in out)


def test_roles_prefix():
    out = suggest_roles("backend")
    assert out
    assert any("backend" in r.lower() for r in out)
