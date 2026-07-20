"""One-time builder: Cubicals curated_skills.json → hireloop/src/data/skills.json.

Runtime does not import Cubicals — only this script reads the monorepo path.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CUBICALS = Path(__file__).resolve().parents[2]
SRC = CUBICALS / "apps" / "api" / "data" / "esco" / "curated_skills.json"
OUT = ROOT / "src" / "data" / "skills.json"

# Cubicals category → Phase 2 category names
_CATEGORY_MAP = {
    "programming_languages": "programming_language",
    "frameworks_libraries": "framework",
    "databases_storage": "database",
    "cloud_devops": "devops",
    "ai_ml": "ai_ml",
    "cs_fundamentals": "cs_concept",
    "system_design": "cs_concept",
    "tools_platforms": "platform",
}

# Extra aliases needed for JD phrasing / Phase 2 tests
_EXTRA_ALIASES: dict[str, list[str]] = {
    "Go": ["golang"],
    "Kubernetes": ["k8s", "kube"],
    "GCP": ["google cloud platform", "google cloud"],
    "PostgreSQL": ["postgres", "psql", "postgresql"],
    "Python": ["python3", "python 3", "py"],
    "React": ["react.js", "reactjs"],
    "Angular": ["angularjs", "angular.js"],
    "Docker": ["docker compose"],
    "SQL": ["structured query language"],
    "AI": ["artificial intelligence"],
    "C": ["c language", "c programming"],
    "R": ["r language", "r programming"],
}


def main() -> None:
    raw = json.loads(SRC.read_text(encoding="utf-8"))
    out: list[dict] = []
    seen: set[str] = set()

    for row in raw:
        if row.get("category") == "soft_skills":
            continue
        name = (row.get("name") or "").strip()
        if not name or name.lower() in seen:
            continue
        cat = _CATEGORY_MAP.get(row.get("category") or "", "platform")
        aliases = [a for a in (row.get("aliases") or []) if a and a.lower() != name.lower()]
        for extra in _EXTRA_ALIASES.get(name, []):
            if extra.lower() != name.lower() and extra.lower() not in {
                a.lower() for a in aliases
            }:
                aliases.append(extra)
        seen.add(name.lower())
        out.append({"canonical": name, "category": cat, "aliases": aliases})

    # Ensure short ambiguous names exist even if upstream drifts
    for canonical, aliases in (
        ("AI", ["artificial intelligence"]),
    ):
        if canonical.lower() not in seen:
            out.append(
                {
                    "canonical": canonical,
                    "category": "ai_ml",
                    "aliases": aliases,
                }
            )
            seen.add(canonical.lower())

    out.sort(key=lambda x: x["canonical"].lower())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(out)} skills → {OUT}")


if __name__ == "__main__":
    main()
