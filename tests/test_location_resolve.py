from src.services.job_service import _resolve_location_filter


def test_united_states_maps_to_country_us():
    assert _resolve_location_filter("United states", {}) == (None, None, False, "US")
    assert _resolve_location_filter("USA", {})[3] == "US"
    assert _resolve_location_filter("us", {})[3] == "US"


def test_remote_and_city_unchanged():
    assert _resolve_location_filter("Remote", {}) == (None, None, True, None)
    city, metro, is_remote, country = _resolve_location_filter("Austin", {})
    assert city == "Austin"
    assert metro is None
    assert is_remote is False
    assert country is None
