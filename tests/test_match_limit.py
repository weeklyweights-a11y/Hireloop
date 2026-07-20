"""Match limit / offset clamping."""

from src.schemas.matching import MatchFilters, clamp_match_limit


def test_clamp_match_limit_bounds():
    assert clamp_match_limit(None) == 20
    assert clamp_match_limit(1) == 1
    assert clamp_match_limit(50) == 50
    assert clamp_match_limit(51) == 50


def test_match_filters_offset_default():
    assert MatchFilters().offset == 0
    assert MatchFilters(offset=40, limit=20).offset == 40
