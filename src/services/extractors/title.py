import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz

_NON_ALNUM = re.compile(r"[^a-z0-9\s\-]+")
_MULTI_SPACE = re.compile(r"\s+")
_PAREN = re.compile(r"\(([^)]*)\)")
_COMPANY_PREFIX = re.compile(
    r"^(?:hiring\s*:?\s*)?([a-z0-9&.\']+)\s+[\-–—|:]\s+(.+)$",
    re.IGNORECASE,
)
_DEPT_PREFIX = re.compile(r"^([^-–—:|]+?)\s*[-–—:|]\s*(.+)$")
# Dash needs whitespace on at least one side so in-word hyphens ("Sign-On",
# "E-Commerce") aren't treated as separators
_DASH_SEP = re.compile(r"\s[-–—|]\s*|[-–—|]\s+")
_COMMA_SEP = re.compile(r",\s*")
_REGION = re.compile(
    r"^(?:amer|emea|apac|latam)(?:\s+(?:east|west|north|south|central))?$"
    r"|^(?:east|west|north|south)$",
    re.IGNORECASE,
)
_LEVEL = re.compile(r"\b(?:iv|v|i{1,3}|l[3-7]|t[3-5]|ic[3-5])\b", re.IGNORECASE)
_COMPANY_SUFFIX = re.compile(
    r"\b(?:inc|llc|llp|corp|corporation|ltd|company|enterprises|holdings|group)\b\.?",
    re.IGNORECASE,
)
# Trailing promo segments ("- sign-on bonus available", "- 4 day work week!")
_PROMO = re.compile(
    r"\b(?:bonus|urgently|hiring now|per hour|benefits|work week|sign.on|no experience)\b|\$",
    re.IGNORECASE,
)
# Trailing work-arrangement / licensure qualifiers ("- Part Time", "- NY Licensed")
_QUALIFIER = re.compile(
    r"^(?:part[- ]?time|full[- ]?time|seasonal|remote|hybrid|on-?site|contract(?:or)?"
    r"|temp(?:orary)?|hourly|entry[- ]?level|per diem"
    r"|\d(?:st|nd|rd|th)\s+shift|(?:day|night|overnight|weekend)s?\s+shift"
    r"|(?:[a-z]{2}\s+)?licensed)$",
    re.IGNORECASE,
)
_DEPARTMENTS = frozenset(
    {
        "engineering", "platform", "data science", "data", "growth", "product",
        "design", "marketing", "sales", "security", "infrastructure", "operations",
        "ops", "finance", "legal", "people", "hr", "human resources", "it",
        "technology", "clinical", "r&d", "research", "analytics", "customer success",
        "support", "supply chain", "corporate", "commercial", "digital", "cloud",
        "payments", "ads", "search", "trust and safety",
    }
)
_SHORT_TITLES = frozenset(
    {"swe", "sde", "mle", "sre", "qa", "pm", "tpm", "em", "ae", "ux", "ui", "it", "hr"}
)
# Shared title boilerplate — ignore when checking content overlap
_GENERIC = frozenset(
    {
        "of", "the", "and", "a", "an", "i", "ii", "iii", "iv", "sr", "senior",
        "junior", "jr", "staff", "principal", "lead", "chief", "officer", "manager",
        "engineer", "engineering", "director", "specialist", "analyst", "associate",
        "coordinator", "head", "vp", "vice", "president", "team",
    }
)


@dataclass
class TitleComponents:
    """Structured pieces stripped from a raw title. title_raw is never mutated —
    these are copies; `clean` is what goes through fuzzy matching."""

    clean: str
    metadata: list[str] = field(default_factory=list)  # parentheticals + noise segments
    region: str | None = None  # "AMER East", "EMEA", ...
    level: str | None = None  # "II", "L5", "IC4", ... as written
    department: str | None = None  # "Engineering", "Data Science", ...


def parse_title_components(raw_title: str) -> TitleComponents:
    comps = TitleComponents(clean="")
    text = raw_title.strip()

    # 1. Parentheticals -> metadata (or region if they look like one)
    def _take_paren(m: re.Match) -> str:
        inner = m.group(1).strip()
        if inner:
            if comps.region is None and _REGION.match(inner):
                comps.region = inner
            else:
                comps.metadata.append(inner)
        return " "

    text = _PAREN.sub(_take_paren, text)

    # 2. Trailing dash segments: regions, departments, company names, promo,
    #    qualifiers. Segments keep internal commas ("Michels Power, Inc.") so a
    #    multi-word company name is stripped whole.
    def _classify(seg: str, allow_department: bool = True) -> bool:
        if comps.region is None and _REGION.match(seg):
            comps.region = seg
        elif allow_department and comps.department is None and seg.lower() in _DEPARTMENTS:
            comps.department = seg
        elif _COMPANY_SUFFIX.search(seg) or _PROMO.search(seg) or _QUALIFIER.match(seg):
            comps.metadata.append(seg)
        else:
            return False
        return True

    while True:
        seps = list(_DASH_SEP.finditer(text))
        if not seps:
            break
        m = seps[-1]
        seg = text[m.end() :].strip()
        if not seg or not _classify(seg):
            break
        text = text[: m.start()].strip()

    # 3. Trailing comma segments: regions, qualifiers, and known departments —
    #    but only strip a department when a multi-word role remains, so
    #    "Manager, Engineering" keeps its one informative suffix
    while True:
        seps = list(_COMMA_SEP.finditer(text))
        if not seps:
            break
        m = seps[-1]
        seg = text[m.end() :].strip()
        remainder = text[: m.start()].strip()
        multiword = len(remainder.split()) >= 2
        if not seg or _COMPANY_SUFFIX.search(seg) or not _classify(seg, allow_department=multiword):
            break
        text = remainder

    # 4. Department prefix before dash/colon ("Engineering - Backend Engineer")
    m = _DEPT_PREFIX.match(text)
    if m and m.group(1).strip().lower() in _DEPARTMENTS and m.group(2).strip():
        comps.department = m.group(1).strip()
        text = m.group(2).strip()

    # 5. Level indicators anywhere ("Engineer II", "SWE L5"); keep first as-is
    m = _LEVEL.search(text)
    if m:
        comps.level = m.group(0)
        text = _LEVEL.sub(" ", text)

    comps.clean = _MULTI_SPACE.sub(" ", text).strip(" -–—:|,")
    return comps


def _canon(text: str) -> str:
    """Lowercase + strip punctuation for fuzzy comparison."""
    text = text.strip().lower()
    m = _COMPANY_PREFIX.match(text)
    if m:
        left, right = m.group(1).lower(), m.group(2)
        if left not in _SHORT_TITLES and len(left) > 3:
            text = right
    text = _NON_ALNUM.sub(" ", text)
    return _MULTI_SPACE.sub(" ", text).strip()


def _specific_tokens(text: str) -> set[str]:
    return {t for t in text.split() if t not in _GENERIC and len(t) > 1}


def normalize_title(
    raw_title: str, taxonomy: list[dict]
) -> tuple[str | None, str | None]:
    """Return (canonical, function) or (None, None) if no match above threshold."""
    if not raw_title or not taxonomy:
        return (None, None)

    cleaned = _canon(parse_title_components(raw_title).clean)
    if not cleaned:
        return (None, None)

    first = cleaned.split()[0]
    title_tokens = set(cleaned.split())
    best_key: tuple | None = None
    best: tuple[str, str] | None = None

    for entry in taxonomy:
        canonical = entry["canonical"]
        function = entry.get("function") or ""
        candidates = [canonical.lower(), *(a.lower() for a in entry.get("aliases", []))]
        for candidate in candidates:
            set_score = fuzz.token_set_ratio(cleaned, candidate)
            if set_score < 75:
                continue
            sort_score = fuzz.token_sort_ratio(cleaned, candidate)
            short_first = candidate == first and len(candidate) <= 4
            # A full multi-word candidate contained in a longer title is a real
            # hit even when the extra tokens wreck the sort ratio ("sr forward
            # deployed engineer, comms & media" -> "forward deployed engineer")
            subset_hit = set_score == 100 and len(candidate.split()) >= 2
            if not short_first and not subset_hit and sort_score < 70:
                continue
            # Reject shared-boilerplate-only hits (Chief Banana ≈ Chief Analytics)
            if not short_first:
                specific = _specific_tokens(candidate)
                if specific and not (specific & title_tokens):
                    continue
            key = (set_score, 1 if short_first else 0, sort_score, len(candidate))
            if best_key is None or key > best_key:
                best_key = key
                best = (canonical, function)

    if best is None:
        return (None, None)
    return best
