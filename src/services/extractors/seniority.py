import re

from src.services.extractors.experience import extract_experience

_TITLE_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("intern", re.compile(r"\bintern(?:ship)?\b", re.IGNORECASE)),
    ("junior", re.compile(
        r"\b(?:junior|jr\.?|associate|entry[\s-]level|new\s+grad)\b", re.IGNORECASE
    )),
    ("senior", re.compile(r"\b(?:senior|sr\.?)\b", re.IGNORECASE)),
    ("staff", re.compile(r"\bstaff\b", re.IGNORECASE)),
    ("principal", re.compile(r"\bprincipal\b", re.IGNORECASE)),
    ("lead", re.compile(r"\b(?:team\s+lead|lead)\b", re.IGNORECASE)),
    ("director", re.compile(r"\bdirector\b", re.IGNORECASE)),
    ("vp", re.compile(r"\b(?:vp|vice\s+president)\b", re.IGNORECASE)),
]


def extract_seniority(title: str, description: str) -> str | None:
    for level, pattern in _TITLE_RULES:
        if pattern.search(title or ""):
            return level

    exp_min, _ = extract_experience(description or "")
    if exp_min is None:
        if re.search(r"entry[\s-]level|new\s+grad", description or "", re.IGNORECASE):
            return "junior"
        return None
    if exp_min <= 1:
        return "junior"
    if exp_min <= 4:
        return "mid"
    if exp_min <= 7:
        return "senior"
    if exp_min <= 10:
        return "staff"
    return "principal"
