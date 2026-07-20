from src.schemas.resume import ResumeParseRequest
from src.services.resume_parse import parse_resume


def test_parse_extracts_skills_from_text():
    text = """
    Jane Doe
    jane@example.com
    https://linkedin.com/in/janedoe
    https://github.com/jane
    San Francisco, CA
    5 years of experience

    Backend Engineer at Stripe
    Skills: Python, Flask, AWS, Docker, PostgreSQL
    """
    out = parse_resume(resume_text=text)
    assert "Python" in out["skills"] or any("python" in s.lower() for s in out["skills"])
    assert out["contact"]["email"] == "jane@example.com"
    assert out["experience_years"] == 5
    assert out["location"] in (None, "San Francisco") or "Francisco" in (out["location"] or "")
    assert out["market_fit"] is None
    assert isinstance(out["inferred"], list)


def test_parse_from_skills_only_expands():
    out = parse_resume(skills=["Python", "Flask"])
    assert out["skills"] == ["Python", "Flask"]
    assert isinstance(out["inferred"], list)


def test_parse_request_schema():
    m = ResumeParseRequest(resume_text="hello")
    assert m.resume_text == "hello"
