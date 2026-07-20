import re

_INTERNSHIP = re.compile(r"\b(?:internship|intern)\b", re.IGNORECASE)
_CONTRACT = re.compile(r"\b(?:contract(?:or)?|freelance)\b", re.IGNORECASE)
_PART_TIME = re.compile(r"\bpart[\s-]time\b", re.IGNORECASE)
_TEMPORARY = re.compile(r"\b(?:temporary|temp)\b", re.IGNORECASE)


def extract_employment_type(title: str, description: str) -> str:
    blob = f"{title or ''} {description or ''}"
    if _INTERNSHIP.search(title or ""):
        return "internship"
    if _CONTRACT.search(blob):
        return "contract"
    if _PART_TIME.search(blob):
        return "part_time"
    if _TEMPORARY.search(blob):
        return "temporary"
    return "full_time"
