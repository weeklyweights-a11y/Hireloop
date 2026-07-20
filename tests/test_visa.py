from src.services.extractors.visa import extract_visa_sponsorship


def test_sponsors_available():
    assert extract_visa_sponsorship("Visa sponsorship is available") == "sponsors"


def test_no_sponsorship():
    assert extract_visa_sponsorship("We are unable to sponsor visas") == "no_sponsorship"


def test_us_only_authorized():
    assert (
        extract_visa_sponsorship("Must be authorized to work in the United States")
        == "us_only"
    )


def test_us_only_green_card():
    assert (
        extract_visa_sponsorship("US Citizenship or Green Card required") == "us_only"
    )


def test_unknown_empty():
    assert extract_visa_sponsorship("") == "unknown"


def test_h1b_sponsors():
    assert (
        extract_visa_sponsorship("H-1B sponsorship available for qualified candidates")
        == "sponsors"
    )
