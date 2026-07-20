import json
from pathlib import Path

from src.services.extractors.title import normalize_title, parse_title_components

TAXONOMY = json.loads(
    (Path(__file__).resolve().parents[1] / "src" / "data" / "title_taxonomy.json").read_text(
        encoding="utf-8"
    )
)


def test_senior_backend_engineer():
    assert normalize_title("Senior Backend Engineer", TAXONOMY) == (
        "Backend Engineer",
        "engineering",
    )


def test_sr_software_developer():
    assert normalize_title("Sr. Software Developer", TAXONOMY) == (
        "Software Engineer",
        "engineering",
    )


def test_ml_engineer_ii():
    assert normalize_title("ML Engineer II", TAXONOMY) == (
        "Machine Learning Engineer",
        "data",
    )


def test_data_scientist_nlp():
    assert normalize_title("Data Scientist - NLP Team", TAXONOMY) == (
        "Data Scientist",
        "data",
    )


def test_stripe_prefix():
    assert normalize_title("Stripe - Backend Engineer, Payments", TAXONOMY) == (
        "Backend Engineer",
        "engineering",
    )


def test_vp_of_engineering():
    assert normalize_title("VP of Engineering", TAXONOMY) == (
        "VP of Engineering",
        "management",
    )


def test_customer_success_manager():
    assert normalize_title("Customer Success Manager", TAXONOMY) == (
        "Customer Success Manager",
        "business",
    )


def test_no_match():
    assert normalize_title("Chief Banana Officer", TAXONOMY) == (None, None)


def test_sde():
    assert normalize_title("SDE", TAXONOMY) == ("Software Engineer", "engineering")


def test_swe_infrastructure():
    assert normalize_title("SWE - Infrastructure", TAXONOMY) == (
        "Software Engineer",
        "engineering",
    )


# --- component parsing ---


def test_components_parenthetical():
    c = parse_title_components("Solutions Engineer (GSI) (Remote)")
    assert c.clean == "Solutions Engineer"
    assert c.metadata == ["GSI", "Remote"]


def test_components_region_paren():
    c = parse_title_components("Account Executive (AMER East)")
    assert c.clean == "Account Executive"
    assert c.region == "AMER East"


def test_components_region_trailing():
    c = parse_title_components("Sales Manager - EMEA")
    assert c.clean == "Sales Manager"
    assert c.region == "EMEA"


def test_components_level():
    c = parse_title_components("Software Engineer II")
    assert c.clean == "Software Engineer"
    assert c.level == "II"
    c = parse_title_components("SWE L5")
    assert c.clean == "SWE"
    assert c.level == "L5"


def test_components_department_prefix():
    c = parse_title_components("Engineering - Backend Engineer")
    assert c.clean == "Backend Engineer"
    assert c.department == "Engineering"
    c = parse_title_components("Data Science: NLP Engineer")
    assert c.clean == "NLP Engineer"
    assert c.department == "Data Science"


def test_components_trailing_company():
    c = parse_title_components("HSE Coordinator - Micon Group, Inc.")
    assert c.clean == "HSE Coordinator"
    assert "Micon Group" in " ".join(c.metadata)


def test_components_trailing_promo():
    c = parse_title_components("Primary Care Physician - Sign-On Bonus Available")
    assert c.clean == "Primary Care Physician"


def test_components_keep_informative_suffix():
    c = parse_title_components("Senior Software Engineer, Backend")
    assert c.clean == "Senior Software Engineer, Backend"


def test_normalize_uses_cleaned_title():
    assert normalize_title("Engineering - Backend Engineer III (Remote)", TAXONOMY) == (
        "Backend Engineer",
        "engineering",
    )
    assert normalize_title("Litigation Paralegal", TAXONOMY) == (
        "Paralegal",
        "legal",
    )
    assert normalize_title("CDL A Local Truck Driver", TAXONOMY) == (
        "Truck Driver",
        "logistics",
    )
