from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "locations.json"
_CACHED: dict | None = None


def _load_locations() -> dict:
    global _CACHED
    if _CACHED is None:
        import json

        _CACHED = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    return _CACHED


@dataclass(frozen=True)
class LocationResult:
    city: str | None
    state: str | None
    country: str
    is_remote: bool
    metro_area: str | None


def _state_maps(data: dict) -> tuple[dict[str, str], set[str]]:
    abbrevs = {k.lower(): v for k, v in data.get("state_abbreviations", {}).items()}
    valid = set(abbrevs.values())
    return abbrevs, valid


def _to_state(token: str, abbrevs: dict[str, str], valid: set[str]) -> str | None:
    t = token.strip()
    if t.upper() in valid:
        return t.upper()
    return abbrevs.get(t.lower())


def _apply_city_alias(token: str, aliases: dict[str, str]) -> str:
    # Longest alias first so "Bay Area" / "New York" beat shorter keys
    lower_map = {k.lower(): v for k, v in aliases.items()}
    key = token.strip().lower()
    if key in lower_map:
        return lower_map[key]
    return token.strip()


def _find_metro(city: str | None, metro_areas: dict[str, list[str]]) -> str | None:
    if not city:
        return None
    for metro, cities in metro_areas.items():
        if any(city.lower() == c.lower() for c in cities):
            return metro
    return None


def _detect_country(
    raw: str,
    city: str | None,
    state: str | None,
    data: dict,
) -> str:
    if state:
        return "US"

    lower = raw.lower()
    # Prefer longer country aliases
    aliases = sorted(
        data.get("country_aliases", {}).items(),
        key=lambda kv: len(kv[0]),
        reverse=True,
    )
    for alias, code in aliases:
        # Word-ish match; avoid matching lone "US" inside other words
        a = alias.lower()
        if a in {"us", "uk"}:
            if re.search(rf"(?<![A-Za-z]){re.escape(a)}(?![A-Za-z])", lower):
                return code
        elif a in lower:
            return code

    non_us = data.get("non_us_city_country", {})
    if city:
        for name, code in non_us.items():
            if city.lower() == name.lower():
                return code
    for name, code in non_us.items():
        if name.lower() in lower:
            return code

    return "US"


def normalize_location(
    raw_location: str | None, locations_data: dict | None = None
) -> LocationResult:
    data = locations_data if locations_data is not None else _load_locations()
    empty = LocationResult(None, None, "US", False, None)
    if not raw_location or not str(raw_location).strip():
        return empty

    raw = str(raw_location).strip()
    is_remote = "remote" in raw.lower()

    aliases = data.get("city_aliases", {})
    defaults = data.get("city_default_states", {})
    abbrevs, valid = _state_maps(data)
    metro_areas = data.get("metro_areas", {})

    # Strip leading/trailing "Remote - " noise but keep remainder
    work = re.sub(r"(?i)^\s*remote(?:\s*[-–,|]\s*|\s+)", "", raw).strip()
    work = re.sub(r"(?i)(?:\s*[-–,|]\s*|\s+)remote\s*$", "", work).strip()
    if work.lower() == "remote":
        work = ""

    if not work:
        return LocationResult(None, None, "US", is_remote, None)

    # Whole-string alias (Bay Area, NYC, Silicon Valley)
    aliased_whole = _apply_city_alias(work, aliases)
    if aliased_whole != work and "," not in work:
        city = aliased_whole
        state = defaults.get(city)
        metro = _find_metro(city, metro_areas)
        country = _detect_country(raw, city, state, data)
        return LocationResult(city, state, country, is_remote, metro)

    parts = [p.strip() for p in work.split(",") if p.strip()]
    # Drop trailing country tokens — keep if the token is also a known city (Singapore)
    country_alias_keys = {k.lower() for k in data.get("country_aliases", {})}
    non_us_cities = {k.lower() for k in data.get("non_us_city_country", {})}
    while parts and parts[-1].lower() in country_alias_keys:
        token = parts[-1].lower()
        if token in non_us_cities and len(parts) == 1:
            break
        parts.pop()

    city: str | None = None
    state: str | None = None

    if not parts:
        country = _detect_country(raw, None, None, data)
        return LocationResult(None, None, country, is_remote, None)

    if len(parts) == 1:
        only = _apply_city_alias(parts[0], aliases)
        st = _to_state(only, abbrevs, valid)
        if st:
            state = st
        else:
            city = only
            state = defaults.get(city)
    else:
        city = _apply_city_alias(parts[0], aliases)
        state = _to_state(parts[1], abbrevs, valid)
        if state is None and len(parts) >= 2:
            # "City, Something" where something isn't a state — keep as city only
            pass
        if state is None:
            state = defaults.get(city)

    metro = _find_metro(city, metro_areas)
    country = _detect_country(raw, city, state, data)
    return LocationResult(city, state, country, is_remote, metro)


def split_location(location_str: str | None) -> tuple[str | None, str | None]:
    """Phase 1 compatibility wrapper."""
    result = normalize_location(location_str)
    return (result.city, result.state)
