import re

_SPONSORS = re.compile(
    r"visa sponsorship (?:is )?available|will sponsor|sponsorship provided|"
    r"h-?1b sponsorship|sponsorship (?:may be )?available",
    re.IGNORECASE,
)
_NO_SPONSOR = re.compile(
    r"no visa sponsorship|will not sponsor|unable to sponsor|cannot sponsor|"
    r"not able to sponsor",
    re.IGNORECASE,
)
_US_ONLY = re.compile(
    r"must be authorized to work in the (?:us|u\.s\.|united states)|"
    r"us citizen|green card|permanent resident required|"
    r"security clearance required",
    re.IGNORECASE,
)


def extract_visa_sponsorship(description: str) -> str:
    text = description or ""
    if _SPONSORS.search(text):
        return "sponsors"  # wins even if US-only language also present
    if _NO_SPONSOR.search(text):
        return "no_sponsorship"
    if _US_ONLY.search(text):
        return "us_only"
    return "unknown"
