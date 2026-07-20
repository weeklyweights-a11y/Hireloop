import json
from pathlib import Path

from src.services.extractors.skills import extract_skills

VOCAB = json.loads(
    (Path(__file__).resolve().parents[1] / "src" / "data" / "skills.json").read_text(
        encoding="utf-8"
    )
)


def test_required_inline():
    req, nice = extract_skills(
        "Experience with Python and PostgreSQL required", VOCAB
    )
    assert req == ["Python", "PostgreSQL"]
    assert nice == []


def test_required_and_nice_sections():
    req, nice = extract_skills(
        "Must have: Python, SQL. Nice to have: Docker, Kubernetes", VOCAB
    )
    assert req == ["Python", "SQL"]
    assert nice == ["Docker", "Kubernetes"]


def test_golang_alias():
    req, nice = extract_skills("golang", VOCAB)
    assert req == ["Go"]
    assert nice == []


def test_k8s_alias():
    req, nice = extract_skills("k8s experience", VOCAB)
    assert req == ["Kubernetes"]
    assert nice == []


def test_react_angular():
    req, nice = extract_skills("Experience with React and Angular", VOCAB)
    assert req == ["React", "Angular"]
    assert nice == []


def test_gcp_alias():
    req, nice = extract_skills("Google Cloud Platform", VOCAB)
    assert req == ["GCP"]
    assert nice == []


def test_go_not_inside_going():
    req, nice = extract_skills("going forward", VOCAB)
    assert req == []
    assert nice == []


def test_empty():
    assert extract_skills("", VOCAB) == ([], [])


def test_no_known_skills():
    assert extract_skills("We value kindness and curiosity", VOCAB) == ([], [])


def test_overlap_required_wins():
    text = (
        "Requirements:\nPython\n\nNice to have:\nPython, Docker"
    )
    req, nice = extract_skills(text, VOCAB)
    assert "Python" in req
    assert "Python" not in nice
    assert "Docker" in nice
