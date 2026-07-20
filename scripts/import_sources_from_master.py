"""One-time import: ../docs/us-career-api-endpoints.json -> src/data/sources/*.json.

Only entries with status == "found" and a job_list_api.url are imported.
Greenhouse/Lever/Ashby get standard configs; Workday/custom copy the master's
method/headers/body/field_mapping verbatim (no invented paths — validation
deactivates anything that doesn't respond with mappable jobs).
"""

import json
import re
from pathlib import Path
from urllib.parse import urlparse

MASTER = Path(__file__).resolve().parents[2] / "docs" / "us-career-api-endpoints.json"
OUT_DIR = Path(__file__).resolve().parents[1] / "src" / "data" / "sources"

GREENHOUSE_MAPPING = {
    "id": "id",
    "title": "title",
    "location": "location.name",
    "description": "content",
    "apply_url": "absolute_url",
    "department": "departments[0].name",
    "updated_at": "updated_at",
}
LEVER_MAPPING = {
    "id": "id",
    "title": "text",
    "location": "categories.location",
    "description": "descriptionPlain",
    "apply_url": "hostedUrl",
    "department": "categories.department",
    "updated_at": "createdAt",
}
ASHBY_MAPPING = {
    "id": "id",
    "title": "title",
    "location": "location",
    "description": "descriptionHtml",
    "apply_url": "jobUrl",
    "department": "department",
    "updated_at": "publishedAt",
}

# master field_mapping key -> our config key (first match wins)
MASTER_KEY_ALIASES = {
    "id": ["id", "job_id", "req_id"],
    "title": ["title"],
    "location": ["location"],
    "description": ["description"],
    "apply_url": ["apply_url", "url", "link"],
    "department": ["department", "category", "team", "function"],
    "updated_at": ["posted_date", "posted", "posted_on", "posted_ts"],
}


def bucket(ats: str | None) -> str:
    a = (ats or "").lower()
    if "greenhouse" in a:
        return "greenhouse"
    if "lever" in a:
        return "lever"
    if "ashby" in a:
        return "ashby"
    if "workday" in a or "myworkday" in a:
        return "workday"
    return "custom"


def slugify(name: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", name.lower())).strip("-")


def website_from(url: str | None) -> str | None:
    if not url:
        return None
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}" if p.netloc else None


def normalize_master_mapping(raw: dict) -> tuple[dict, str | None]:
    """Return (field_mapping, response_path) from a master entry's mapping."""
    raw = raw or {}
    root = raw.get("root")
    # roots like "results (HTML fragment string; ...)" are notes, not paths
    if root and not re.fullmatch(r"[\w.\[\]]+", root):
        root = None
    mapping = {}
    for our_key, aliases in MASTER_KEY_ALIASES.items():
        for alias in aliases:
            path = raw.get(alias)
            if isinstance(path, str) and path:
                if root and path.startswith(f"{root}[]."):
                    path = path[len(root) + 3 :]
                mapping[our_key] = path
                break
    return mapping, root


def convert(entry: dict) -> dict:
    ats = bucket(entry.get("ats"))
    api = entry["job_list_api"]
    url = api["url"]
    config = {
        "company_name": entry["name"],
        "company_slug": slugify(entry["name"]),
        "company_website": website_from(entry.get("careers_page_url")),
        "ats_type": ats,
        "api_endpoint": url,
        "api_method": (api.get("method") or "GET").upper(),
        "api_headers": {},
        "api_params": {},
        "api_body": None,
        "response_path": None,
        "field_mapping": {},
        "pagination_config": {"type": "none"},
    }
    if ats == "greenhouse":
        config["api_params"] = {"content": "true"}
        config["response_path"] = "jobs"
        config["field_mapping"] = GREENHOUSE_MAPPING
    elif ats == "lever":
        config["api_params"] = {"mode": "json"}
        config["field_mapping"] = LEVER_MAPPING
        config["pagination_config"] = {"type": "offset", "param": "skip", "limit": 100}
    elif ats == "ashby":
        config["response_path"] = "jobs"
        config["field_mapping"] = ASHBY_MAPPING
    else:  # workday / custom: copy master verbatim, don't invent
        config["api_headers"] = entry.get("headers") or {}
        config["api_body"] = entry.get("request_body")
        mapping, root = normalize_master_mapping(entry.get("field_mapping"))
        config["field_mapping"] = mapping
        config["response_path"] = root
        # ponytail: master pagination is free text; Phase 1 polls first page only
        # for workday/custom. Structured body-offset pagination is a Phase 2 upgrade.
    return config


def main() -> None:
    master = json.loads(MASTER.read_text(encoding="utf-8"))
    found = [
        c
        for c in master["companies"]
        if c.get("status") == "found" and (c.get("job_list_api") or {}).get("url")
    ]

    buckets: dict[str, list[dict]] = {
        "greenhouse": [],
        "lever": [],
        "ashby": [],
        "workday": [],
        "custom": [],
    }
    seen_slugs: dict[str, int] = {}
    for entry in found:
        config = convert(entry)
        slug = config["company_slug"]
        if slug in seen_slugs:
            seen_slugs[slug] += 1
            config["company_slug"] = f"{slug}-{seen_slugs[slug]}"
        else:
            seen_slugs[slug] = 1
        buckets[config["ats_type"]].append(config)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for ats, configs in buckets.items():
        (OUT_DIR / f"{ats}.json").write_text(
            json.dumps(configs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"{ats}: {len(configs)}")
    print(f"total: {sum(len(v) for v in buckets.values())}")

    (OUT_DIR / "README.md").write_text(
        "# Source configs\n\n"
        "Imported from `docs/us-career-api-endpoints.json` (Playwright discovery pipeline, "
        "verified 2026-07) via `scripts/import_sources_from_master.py`. Only `status: found` "
        "entries with a live `job_list_api.url` were imported.\n\n"
        "- greenhouse/lever/ashby: standard public-API configs (uniform across tenants).\n"
        "- workday/custom: method/headers/body/field_mapping copied verbatim from the "
        "verified capture. Configs whose mapping is empty or wrong are deactivated by "
        "`scripts/validate_sources.py`, not hand-fixed.\n"
        "- Phase 1 polls only the first page for workday/custom sources (body-based "
        "pagination lands in Phase 2).\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
