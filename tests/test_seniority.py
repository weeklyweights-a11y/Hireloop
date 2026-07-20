from src.services.extractors.seniority import extract_seniority


def test_senior_from_title():
    assert extract_seniority("Senior Backend Engineer", "") == "senior"


def test_junior_from_title():
    assert extract_seniority("Jr. Data Analyst", "") == "junior"


def test_staff_from_title():
    assert extract_seniority("Staff ML Engineer", "") == "staff"


def test_intern_from_title():
    assert extract_seniority("Software Engineering Intern", "") == "intern"


def test_senior_from_experience():
    assert extract_seniority("Backend Engineer", "5+ years experience") == "senior"


def test_junior_from_entry_level():
    assert extract_seniority("Backend Engineer", "entry level") == "junior"


def test_none_when_unknown():
    assert extract_seniority("Backend Engineer", "") is None
