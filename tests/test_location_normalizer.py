import json
from pathlib import Path

from src.services.extractors.location import normalize_location

DATA = json.loads(
    (Path(__file__).resolve().parents[1] / "src" / "data" / "locations.json").read_text(
        encoding="utf-8"
    )
)


def test_san_francisco_ca():
    r = normalize_location("San Francisco, CA", DATA)
    assert (r.city, r.state, r.country) == ("San Francisco", "CA", "US")
    assert r.is_remote is False


def test_nyc_alias():
    r = normalize_location("NYC", DATA)
    assert r.city == "New York City"
    assert r.state == "NY"
    assert r.country == "US"


def test_mountain_view_metro():
    r = normalize_location("Mountain View, CA", DATA)
    assert r.city == "Mountain View"
    assert r.state == "CA"
    assert r.metro_area == "San Francisco"


def test_remote_only():
    r = normalize_location("Remote", DATA)
    assert r.is_remote is True
    assert r.city is None
    assert r.state is None


def test_remote_with_city():
    r = normalize_location("Remote - San Francisco", DATA)
    assert r.is_remote is True
    assert r.city == "San Francisco"
    assert r.state == "CA"


def test_london_uk():
    r = normalize_location("London, UK", DATA)
    assert r.city == "London"
    assert r.country == "GB"
    assert r.state is None


def test_singapore():
    r = normalize_location("Singapore", DATA)
    assert r.city == "Singapore"
    assert r.country == "SG"


def test_austin_texas():
    r = normalize_location("Austin, Texas", DATA)
    assert (r.city, r.state, r.country) == ("Austin", "TX", "US")


def test_palo_alto_united_states():
    r = normalize_location("Palo Alto, CA, United States", DATA)
    assert r.city == "Palo Alto"
    assert r.state == "CA"
    assert r.metro_area == "San Francisco"
    assert r.country == "US"


def test_empty():
    r = normalize_location("", DATA)
    assert (r.city, r.state, r.country, r.is_remote) == (None, None, "US", False)


def test_none():
    r = normalize_location(None, DATA)
    assert (r.city, r.state, r.country) == (None, None, "US")


def test_bay_area():
    r = normalize_location("Bay Area", DATA)
    assert r.city == "San Francisco"
    assert r.state == "CA"
