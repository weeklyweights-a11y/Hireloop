import re

# $180,000 | $180K | $85 (optionally k-suffixed)
_AMOUNT = r"\$\s*(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*([kK])?"
_SEP = r"\s*(?:-|–|—|to)\s*"
_HOURLY = r"\s*(?:/\s*(?:hour|hr)|per\s+(?:hour|hr))"

_RANGE_HOURLY = re.compile(_AMOUNT + _SEP + _AMOUNT + _HOURLY, re.IGNORECASE)
_RANGE = re.compile(_AMOUNT + _SEP + _AMOUNT)
_SINGLE_HOURLY = re.compile(_AMOUNT + _HOURLY, re.IGNORECASE)
_SINGLE = re.compile(_AMOUNT)
# "Salary: 180,000 - 250,000" — no dollar sign, but explicit salary context
_CONTEXT_RANGE = re.compile(
    r"salary[^\n$]{0,20}?(\d{1,3}(?:,\d{3})+|\d{4,})" + _SEP + r"(\d{1,3}(?:,\d{3})+|\d{4,})",
    re.IGNORECASE,
)

HOURS_PER_YEAR = 40 * 52


def _to_int(num: str, k_suffix: str | None) -> int:
    value = float(num.replace(",", ""))
    if k_suffix:
        value *= 1000
    return int(value)


def extract_salary(text: str) -> tuple[int | None, int | None]:
    if not text:
        return (None, None)

    m = _RANGE_HOURLY.search(text)
    if m:
        lo = _to_int(m.group(1), m.group(2)) * HOURS_PER_YEAR
        hi = _to_int(m.group(3), m.group(4)) * HOURS_PER_YEAR
        return (lo, hi)

    m = _RANGE.search(text)
    if m:
        lo = _to_int(m.group(1), m.group(2))
        hi = _to_int(m.group(3), m.group(4) or m.group(2))
        if lo >= 10_000 and hi >= 10_000:
            return (lo, hi)

    m = _SINGLE_HOURLY.search(text)
    if m:
        rate = _to_int(m.group(1), m.group(2))
        if 10 <= rate <= 500:
            annual = rate * HOURS_PER_YEAR
            return (annual, annual)

    m = _SINGLE.search(text)
    if m:
        value = _to_int(m.group(1), m.group(2))
        # ignore small figures like "$500 bonus" — not an annual salary
        if value >= 10_000:
            return (value, value)

    m = _CONTEXT_RANGE.search(text)
    if m:
        lo = int(m.group(1).replace(",", ""))
        hi = int(m.group(2).replace(",", ""))
        if lo >= 10_000 and hi >= 10_000:
            return (lo, hi)

    return (None, None)
