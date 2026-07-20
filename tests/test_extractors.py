import pytest

from src.services.extractors.experience import extract_experience
from src.services.extractors.html import normalize_for_comparison, strip_html
from src.services.extractors.location import split_location
from src.services.extractors.remote import extract_remote_policy
from src.services.extractors.salary import extract_salary
from src.services.parser import parse_job


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ("<p>Hello</p>", "Hello"),
        ("<li>Item 1</li><li>Item 2</li>", "- Item 1\n- Item 2"),
        ("Hello<br>World", "Hello\nWorld"),
        ("&amp; &lt; &gt; &#x27;", "& < > '"),
        ("plain text with no tags", "plain text with no tags"),
        ("", ""),
        ("<div><strong>Bold</strong>&nbsp;text</div>", "Bold text"),
        ("<p>One</p><p>Two</p>", "One\nTwo"),
        # Greenhouse double-encodes HTML: entities must decode before tag strip
        ("&lt;p&gt;Hello&lt;/p&gt;", "Hello"),
        ("&lt;p&gt;A &amp; B&lt;/p&gt;", "A & B"),
    ],
)
def test_strip_html(html, expected):
    assert strip_html(html) == expected


def test_normalize_for_comparison():
    assert normalize_for_comparison("<p>Hello  World</p>") == normalize_for_comparison(
        "HELLO\nWORLD"
    )
    assert normalize_for_comparison(None) == ""
    assert normalize_for_comparison("<b>same</b>") != normalize_for_comparison("different")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("$180,000 - $250,000", (180000, 250000)),
        ("$180K-$250K", (180000, 250000)),
        ("$180k - $250k", (180000, 250000)),
        ("$85/hour", (176800, 176800)),
        ("$75 - $95/hr", (156000, 197600)),
        ("$180,000/year", (180000, 180000)),
        ("$180,000 to $250,000", (180000, 250000)),
        ("Competitive salary", (None, None)),
        ("", (None, None)),
        ("Base: $180K + 20% bonus", (180000, 180000)),
        ("$200,000 - $300,000 USD annually", (200000, 300000)),
        ("Salary: 180,000 - 250,000", (180000, 250000)),
        ("$500 signing bonus", (None, None)),
    ],
)
def test_extract_salary(text, expected):
    assert extract_salary(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("5+ years of experience", (5, None)),
        ("3-5 years of experience", (3, 5)),
        ("3 to 5 years experience", (3, 5)),
        ("entry level", (0, 1)),
        ("new grad", (0, 1)),
        ("no experience required", (0, 0)),
        ("at least 3 years", (3, None)),
        ("", (None, None)),
        ("3 years of relevant experience", (3, 3)),
        ("10+ years of professional experience", (10, None)),
        ("5 years of industry experience", (5, 5)),
    ],
)
def test_extract_experience(text, expected):
    assert extract_experience(text) == expected


@pytest.mark.parametrize(
    ("title", "desc", "loc", "expected"),
    [
        ("Remote Backend Engineer", "", None, "remote"),
        ("Backend Engineer", "This is a hybrid role", "NYC", "hybrid"),
        ("Backend Engineer", "100% remote position", None, "remote"),
        ("Backend Engineer", "", "San Francisco, CA", "onsite"),
        ("Backend Engineer", "Work from our SF office", "SF", "onsite"),
        ("Backend Engineer", "", "Remote", "remote"),
        ("Backend Engineer", "", None, "unknown"),
        ("Backend Engineer", "3 days in office, 2 days remote", "NYC", "hybrid"),
        ("Backend Engineer", "This role is fully remote", None, "remote"),
        ("Backend Engineer", "on-site presence required", "Austin, TX", "onsite"),
    ],
)
def test_extract_remote_policy(title, desc, loc, expected):
    assert extract_remote_policy(title, desc, loc) == expected


@pytest.mark.parametrize(
    ("loc", "expected"),
    [
        ("San Francisco, CA", ("San Francisco", "CA")),
        ("New York, NY", ("New York City", "NY")),
        ("San Francisco, California", ("San Francisco", "CA")),
        ("Remote", (None, None)),
        ("Remote, US", (None, None)),
        ("Austin, TX, United States", ("Austin", "TX")),
        ("", (None, None)),
        (None, (None, None)),
        ("United States", (None, None)),
        ("Seattle, Washington", ("Seattle", "WA")),
        ("San Francisco, CA, US", ("San Francisco", "CA")),
    ],
)
def test_split_location(loc, expected):
    assert split_location(loc) == expected


def test_parse_job_coordinates_all_extractors():
    parsed = parse_job(
        title="Senior Backend Engineer",
        location="San Francisco, California",
        description="<p>We pay $180,000 - $250,000.</p><p>5+ years of experience. Hybrid.</p>",
    )
    assert parsed.salary_min == 180000
    assert parsed.salary_max == 250000
    assert parsed.experience_min == 5
    assert parsed.experience_max is None
    assert parsed.remote_policy == "hybrid"
    assert parsed.location_city == "San Francisco"
    assert parsed.location_state == "CA"
    assert parsed.description_html.startswith("<p>")
    assert "<p>" not in parsed.description_text
    assert parsed.seniority == "senior"
    assert parsed.title_normalized == "Backend Engineer"
    assert parsed.location_metro == "San Francisco"
    assert parsed.location_country == "US"
    assert parsed.employment_type == "full_time"


def test_parse_job_empty_description():
    parsed = parse_job(title="Engineer", location=None, description=None)
    assert parsed.description_html == ""
    assert parsed.description_text == ""
    assert parsed.salary_min is None
    assert parsed.remote_policy == "unknown"
