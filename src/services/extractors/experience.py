import re

_YEARS = r"years?(?:'|’)?"
_QUALIFIER = r"(?:\s+of)?(?:\s+(?:relevant|professional|industry))?(?:\s+experience)?"

_NO_EXPERIENCE = re.compile(r"no experience required|\b0\s*years?\b", re.IGNORECASE)
_RANGE = re.compile(r"(\d{1,2})\s*(?:-|–|to)\s*(\d{1,2})\s*\+?\s*" + _YEARS, re.IGNORECASE)
_MINIMUM = re.compile(
    r"(?:(\d{1,2})\s*\+\s*" + _YEARS + r"|at least\s+(\d{1,2})\s*" + _YEARS + r"?)",
    re.IGNORECASE,
)
_EXACT = re.compile(r"(\d{1,2})\s*" + _YEARS + _QUALIFIER, re.IGNORECASE)
_ENTRY = re.compile(r"entry[\s-]level|new grad|recent graduate", re.IGNORECASE)


def extract_experience(text: str) -> tuple[int | None, int | None]:
    if not text:
        return (None, None)

    if _NO_EXPERIENCE.search(text):
        return (0, 0)

    m = _RANGE.search(text)
    if m:
        return (int(m.group(1)), int(m.group(2)))

    m = _MINIMUM.search(text)
    if m:
        return (int(m.group(1) or m.group(2)), None)

    m = _EXACT.search(text)
    if m:
        n = int(m.group(1))
        return (n, n)

    if _ENTRY.search(text):
        return (0, 1)

    return (None, None)
