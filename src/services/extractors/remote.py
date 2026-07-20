import re

_DESC_REMOTE = re.compile(
    r"100%\s*remote|fully remote|work from anywhere|remote[\s-]first", re.IGNORECASE
)
_DESC_HYBRID = re.compile(
    r"hybrid|\d\s*days?\s+(?:in[\s-](?:the[\s-])?office|on[\s-]site)", re.IGNORECASE
)
_DESC_ONSITE = re.compile(r"on[\s-]site|in[\s-]office|in office", re.IGNORECASE)
_REMOTE_WORD = re.compile(r"remote", re.IGNORECASE)
_HYBRID_WORD = re.compile(r"hybrid", re.IGNORECASE)


def extract_remote_policy(title: str, description: str, location: str | None) -> str:
    title_loc = f"{title} {location or ''}"
    if _REMOTE_WORD.search(title_loc):
        return "remote"
    if _HYBRID_WORD.search(title_loc):
        return "hybrid"

    description = description or ""
    if _DESC_REMOTE.search(description):
        return "remote"
    if _DESC_HYBRID.search(description):
        return "hybrid"
    if _DESC_ONSITE.search(description) and not _REMOTE_WORD.search(description):
        return "onsite"

    if location and location.strip():
        return "onsite"

    return "unknown"
