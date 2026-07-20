import re
from dataclasses import dataclass

_REQUIRED_HEADERS = re.compile(
    r"(?mi)^(?:#{1,3}\s*)?(?:"
    r"requirements?|required|must have|qualifications?|"
    r"what you.?ll need|minimum qualifications?|basic qualifications?|"
    r"what we.?re looking for|you have|you.?ll need"
    r")\s*:?\s*$"
)
_NICE_HEADERS = re.compile(
    r"(?mi)^(?:#{1,3}\s*)?(?:"
    r"nice to have|preferred(?: qualifications?)?|bonus|plus|desired|"
    r"it would be great if|ideally you also have|preferred skills"
    r")\s*:?\s*$"
)
_INLINE_REQUIRED = re.compile(
    r"(?mi)\b(?:must have|requirements?|required|qualifications?)\s*:\s*"
)
_INLINE_NICE = re.compile(
    r"(?mi)\b(?:nice to have|preferred|bonus|plus)\s*:\s*"
)


@dataclass(frozen=True)
class _SkillPat:
    canonical: str
    pattern: re.Pattern[str]
    needles: tuple[str, ...]
    always_scan: bool  # short names — substring prefilter is unsafe


_COMPILE_CACHE: dict[int, list[_SkillPat]] = {}


def _compile_vocab(skills_vocab: list[dict]) -> list[_SkillPat]:
    # ponytail: cache by list identity — DataLoader keeps one skills list forever
    key = id(skills_vocab)
    cached = _COMPILE_CACHE.get(key)
    if cached is not None:
        return cached

    compiled: list[_SkillPat] = []
    for entry in skills_vocab:
        canonical = entry["canonical"]
        names = [canonical, *(entry.get("aliases") or [])]
        names = sorted({n for n in names if n}, key=len, reverse=True)
        parts: list[str] = []
        needles: list[str] = []
        always = False
        for name in names:
            needles.append(name.lower())
            if len(name) <= 2:
                always = True
                parts.append(rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9])")
            else:
                parts.append(rf"\b{re.escape(name)}\b")
        if not parts:
            continue
        compiled.append(
            _SkillPat(
                canonical=canonical,
                pattern=re.compile("|".join(parts), re.IGNORECASE),
                needles=tuple(needles),
                always_scan=always,
            )
        )
    _COMPILE_CACHE[key] = compiled
    return compiled


def _section_spans(text: str) -> list[tuple[str, int, int]]:
    if not text:
        return []

    markers: list[tuple[int, str]] = []
    for m in _REQUIRED_HEADERS.finditer(text):
        markers.append((m.start(), "required"))
    for m in _NICE_HEADERS.finditer(text):
        markers.append((m.start(), "nice"))
    for m in _INLINE_REQUIRED.finditer(text):
        markers.append((m.start(), "required"))
    for m in _INLINE_NICE.finditer(text):
        markers.append((m.start(), "nice"))

    if not markers:
        return [("required", 0, len(text))]

    markers.sort(key=lambda x: x[0])
    deduped: list[tuple[int, str]] = []
    for pos, kind in markers:
        if deduped and deduped[-1][0] == pos:
            deduped[-1] = (pos, kind)
        else:
            deduped.append((pos, kind))

    spans: list[tuple[str, int, int]] = []
    if deduped[0][0] > 0:
        spans.append(("required", 0, deduped[0][0]))
    for i, (pos, kind) in enumerate(deduped):
        end = deduped[i + 1][0] if i + 1 < len(deduped) else len(text)
        spans.append((kind, pos, end))
    return spans


def _kind_at(spans: list[tuple[str, int, int]], index: int) -> str:
    for kind, start, end in spans:
        if start <= index < end:
            return kind
    return "required"


def extract_skills(
    description: str, skills_vocab: list[dict]
) -> tuple[list[str], list[str]]:
    """Return (required_skills, nice_to_have_skills), ordered by first appearance."""
    if not description or not skills_vocab:
        return ([], [])

    patterns = _compile_vocab(skills_vocab)
    spans = _section_spans(description)
    text_lower = description.lower()

    raw_hits: list[tuple[int, int, str]] = []
    for skill in patterns:
        if not skill.always_scan and not any(n in text_lower for n in skill.needles):
            continue
        for m in skill.pattern.finditer(description):
            raw_hits.append((m.start(), m.end(), skill.canonical))

    raw_hits.sort(key=lambda h: (h[0], -(h[1] - h[0])))
    accepted: list[tuple[int, int, str]] = []
    for start, end, canonical in raw_hits:
        if any(not (end <= a_start or start >= a_end) for a_start, a_end, _ in accepted):
            continue
        accepted.append((start, end, canonical))

    found: dict[str, tuple[str, int]] = {}
    for start, end, canonical in sorted(accepted, key=lambda h: h[0]):
        kind = _kind_at(spans, start)
        prev = found.get(canonical)
        if prev is None:
            found[canonical] = (kind, start)
        elif prev[0] == "nice" and kind == "required":
            found[canonical] = (kind, start)

    required = sorted(
        (c for c, (k, _) in found.items() if k == "required"),
        key=lambda c: found[c][1],
    )
    nice = sorted(
        (c for c, (k, _) in found.items() if k == "nice"),
        key=lambda c: found[c][1],
    )
    return (required, nice)
