"""Generate COMPANIES.md from src/data/sources/*.json (Sector always em dash)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES_DIR = ROOT / "src" / "data" / "sources"
OUT = ROOT / "COMPANIES.md"
SECTOR = "—"


def collect_rows() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for path in sorted(SOURCES_DIR.glob("*.json")):
        for config in json.loads(path.read_text(encoding="utf-8")):
            name = (config.get("company_name") or "").strip()
            ats = (config.get("ats_type") or "").strip() or "unknown"
            if name:
                rows.append((name, ats))
    rows.sort(key=lambda r: r[0].lower())
    # de-dupe by company name (keep first ATS)
    seen: set[str] = set()
    uniq: list[tuple[str, str]] = []
    for name, ats in rows:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append((name, ats))
    return uniq


def render(rows: list[tuple[str, str]]) -> str:
    lines = [
        "# Companies monitored by HireLoop",
        "",
        f"_Generated from source configs ({len(rows)} companies). Sector is not stored in configs._",
        "",
        "| Company | Sector | ATS |",
        "|---|---|---|",
    ]
    for name, ats in rows:
        lines.append(f"| {name} | {SECTOR} | {ats} |")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    text = render(collect_rows())
    OUT.write_text(text, encoding="utf-8")
    print(f"Wrote {OUT} ({text.count(chr(10))} lines)")


if __name__ == "__main__":
    main()
