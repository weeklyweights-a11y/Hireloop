"""Skill expansion unit tests — mocked Neo4j edges (no live graph dependency)."""
from __future__ import annotations

import pytest

from src.services.matching.skill_expander import expand_user_skills


def _edge_runner(edges: list[dict]):
    """edges: {a, b, strength} directed a-[:IMPLIES]->b."""

    def run(cypher: str, **params):
        skill = params.get("skill")
        already = set(params.get("already_found") or [])
        if "()-[:IMPLIES]->(grandparent" in cypher or "[:IMPLIES]->()-[:IMPLIES]->" in cypher:
            # two hop
            out = []
            for e1 in edges:
                if e1["a"] != skill:
                    continue
                mid = e1["b"]
                for e2 in edges:
                    if e2["a"] == mid and e2["b"] not in already and e2["b"] != skill:
                        out.append({"skill": e2["b"], "confidence": 0.7})
            return out
        if "-[r:IMPLIES]-" in cypher or "undirected" in cypher.lower():
            # lateral: undirected, 60 <= strength < 80
            out = []
            for e in edges:
                s = e["strength"]
                if not (60 <= s < 80):
                    continue
                other = None
                if e["a"] == skill:
                    other = e["b"]
                elif e["b"] == skill:
                    other = e["a"]
                if other and other not in already:
                    out.append({"skill": other, "confidence": s * 0.005})
            return out
        # one hop outgoing (strength >= 80 only — weaker edges are lateral)
        out = []
        for e in edges:
            if e["a"] == skill and e["strength"] >= 80:
                out.append(
                    {
                        "skill": e["b"],
                        "strength": e["strength"],
                        "inferred_from": skill,
                    }
                )
        return out

    return run


def test_empty_skills():
    profile = expand_user_skills([])
    assert profile.direct == []
    assert profile.inferred == []
    assert profile.lateral == []
    assert profile.all_skills == []


def test_direct_confidence_one(monkeypatch):
    monkeypatch.setattr(
        "src.services.matching.skill_expander._run_cypher",
        _edge_runner([]),
    )
    monkeypatch.setattr(
        "src.services.matching.skill_expander.is_available", lambda: True
    )
    monkeypatch.setattr(
        "src.services.matching.skill_expander._canonical",
        lambda s: s,
    )
    profile = expand_user_skills(["Python"])
    assert len(profile.direct) == 1
    assert profile.direct[0].confidence == 1.0
    assert profile.direct[0].source == "direct"


def test_one_hop_cnn_to_deep_learning(monkeypatch):
    edges = [{"a": "CNN", "b": "Deep Learning", "strength": 85}]
    monkeypatch.setattr(
        "src.services.matching.skill_expander._run_cypher", _edge_runner(edges)
    )
    monkeypatch.setattr(
        "src.services.matching.skill_expander.is_available", lambda: True
    )
    monkeypatch.setattr(
        "src.services.matching.skill_expander._canonical", lambda s: s
    )
    profile = expand_user_skills(["CNN"])
    names = {s.name: s for s in profile.inferred}
    assert "Deep Learning" in names
    assert names["Deep Learning"].confidence == pytest.approx(0.85 * 0.9)
    assert names["Deep Learning"].confidence < 1.0
    assert names["Deep Learning"].inferred_from == "CNN"


def test_flask_implies_python(monkeypatch):
    edges = [{"a": "Flask", "b": "Python", "strength": 92}]
    monkeypatch.setattr(
        "src.services.matching.skill_expander._run_cypher", _edge_runner(edges)
    )
    monkeypatch.setattr(
        "src.services.matching.skill_expander.is_available", lambda: True
    )
    monkeypatch.setattr(
        "src.services.matching.skill_expander._canonical", lambda s: s
    )
    profile = expand_user_skills(["Flask"])
    assert any(s.name == "Python" for s in profile.inferred)


def test_two_hop(monkeypatch):
    edges = [
        {"a": "CNN", "b": "Deep Learning", "strength": 90},
        {"a": "Deep Learning", "b": "Machine Learning", "strength": 88},
    ]
    monkeypatch.setattr(
        "src.services.matching.skill_expander._run_cypher", _edge_runner(edges)
    )
    monkeypatch.setattr(
        "src.services.matching.skill_expander.is_available", lambda: True
    )
    monkeypatch.setattr(
        "src.services.matching.skill_expander._canonical", lambda s: s
    )
    profile = expand_user_skills(["CNN"])
    ml = next(s for s in profile.inferred if s.name == "Machine Learning")
    assert ml.confidence == 0.7


def test_lateral_band_60_to_80(monkeypatch):
    edges = [{"a": "TensorFlow", "b": "PyTorch", "strength": 65}]
    monkeypatch.setattr(
        "src.services.matching.skill_expander._run_cypher", _edge_runner(edges)
    )
    monkeypatch.setattr(
        "src.services.matching.skill_expander.is_available", lambda: True
    )
    monkeypatch.setattr(
        "src.services.matching.skill_expander._canonical", lambda s: s
    )
    profile = expand_user_skills(["TensorFlow"])
    assert any(s.name == "PyTorch" and s.source == "lateral" for s in profile.lateral)
    lat = next(s for s in profile.lateral if s.name == "PyTorch")
    assert abs(lat.confidence - 65 * 0.005) < 1e-9


def test_strong_edge_not_lateral(monkeypatch):
    edges = [{"a": "TensorFlow", "b": "Python", "strength": 90}]
    monkeypatch.setattr(
        "src.services.matching.skill_expander._run_cypher", _edge_runner(edges)
    )
    monkeypatch.setattr(
        "src.services.matching.skill_expander.is_available", lambda: True
    )
    monkeypatch.setattr(
        "src.services.matching.skill_expander._canonical", lambda s: s
    )
    profile = expand_user_skills(["TensorFlow"])
    assert any(s.name == "Python" for s in profile.inferred)
    assert not any(s.name == "Python" for s in profile.lateral)


def test_dedupe_highest_confidence(monkeypatch):
    edges = [
        {"a": "CNN", "b": "Deep Learning", "strength": 80},
        {"a": "Neural Networks", "b": "Deep Learning", "strength": 95},
    ]
    monkeypatch.setattr(
        "src.services.matching.skill_expander._run_cypher", _edge_runner(edges)
    )
    monkeypatch.setattr(
        "src.services.matching.skill_expander.is_available", lambda: True
    )
    monkeypatch.setattr(
        "src.services.matching.skill_expander._canonical", lambda s: s
    )
    profile = expand_user_skills(["CNN", "Neural Networks"])
    dl = [s for s in profile.inferred if s.name == "Deep Learning"]
    assert len(dl) == 1
    assert abs(dl[0].confidence - 0.95 * 0.9) < 1e-9


def test_unknown_skill_direct_only(monkeypatch):
    monkeypatch.setattr(
        "src.services.matching.skill_expander._run_cypher", _edge_runner([])
    )
    monkeypatch.setattr(
        "src.services.matching.skill_expander.is_available", lambda: True
    )
    monkeypatch.setattr(
        "src.services.matching.skill_expander._canonical", lambda s: s
    )
    profile = expand_user_skills(["TotallyFakeSkillXYZ"])
    assert len(profile.direct) == 1
    assert profile.inferred == []
    assert profile.lateral == []


def test_graph_unavailable_direct_only(monkeypatch):
    monkeypatch.setattr(
        "src.services.matching.skill_expander.is_available", lambda: False
    )
    monkeypatch.setattr(
        "src.services.matching.skill_expander._canonical", lambda s: s
    )
    profile = expand_user_skills(["Python", "SQL"])
    assert len(profile.direct) == 2
    assert profile.inferred == []
    assert profile.lateral == []
