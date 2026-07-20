from src.services.extractors.employment_type import extract_employment_type


def test_internship():
    assert extract_employment_type("Software Engineering Intern", "") == "internship"


def test_contract():
    assert (
        extract_employment_type("Backend Engineer", "This is a contract position")
        == "contract"
    )


def test_part_time():
    assert extract_employment_type("Part-Time Data Analyst", "") == "part_time"


def test_full_time_explicit():
    assert extract_employment_type("Backend Engineer", "Full-time role") == "full_time"


def test_full_time_default():
    assert extract_employment_type("Backend Engineer", "") == "full_time"
