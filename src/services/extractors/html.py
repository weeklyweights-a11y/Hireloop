import html as html_lib
import re

_BREAKS = re.compile(r"<\s*(?:br\s*/?|/p|/li)\s*>", re.IGNORECASE)
_LI_OPEN = re.compile(r"<\s*li[^>]*>", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
# Greenhouse et al. double-encode their HTML content (&lt;p&gt;...). Detect an
# encoded tag (&lt; directly before a letter or slash) so we unescape before
# stripping — without touching plain entities like "&lt; " that mean a literal "<".
_ENCODED_TAG = re.compile(r"&lt;/?[a-zA-Z]")


def strip_html(text: str) -> str:
    if not text:
        return ""
    if _ENCODED_TAG.search(text):
        text = html_lib.unescape(text)
    text = _BREAKS.sub("\n", text)
    text = _LI_OPEN.sub("- ", text)
    text = _TAG.sub("", text)
    text = html_lib.unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def normalize_for_comparison(text: str | None) -> str:
    """Strip HTML, lowercase, collapse all whitespace — so formatting-only
    changes in a description don't count as an update."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", strip_html(text).lower()).strip()
