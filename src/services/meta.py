"""Suggest locations / roles for the web UI."""

from __future__ import annotations

from src.services.data_loader import DataLoader


def suggest_locations(q: str | None = None, *, limit: int = 20) -> list[str]:
    data = DataLoader.get().locations
    cities: set[str] = set(data.get("city_default_states", {}).keys())
    cities.update(data.get("city_aliases", {}).values())
    cities.update(data.get("city_aliases", {}).keys())
    needle = (q or "").strip().lower()
    ranked = sorted(cities, key=str.lower)
    if needle and needle != "remote":
        ranked = [c for c in ranked if needle in c.lower()]
    out = ["Remote"]
    for c in ranked:
        if c.lower() == "remote":
            continue
        out.append(c)
        if len(out) >= limit:
            break
    return out


def suggest_roles(q: str | None = None, *, limit: int = 20) -> list[str]:
    taxonomy = DataLoader.get().taxonomy
    needle = (q or "").strip().lower()
    names: list[str] = []
    seen: set[str] = set()
    for entry in taxonomy:
        canonical = entry.get("canonical") or ""
        candidates = [canonical, *(entry.get("aliases") or [])]
        for name in candidates:
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            if needle and needle not in key:
                continue
            seen.add(key)
            names.append(name)
            if len(names) >= limit:
                return names
    return names
