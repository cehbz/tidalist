import pytest

from tidalist.core.recording import Candidate
from tidalist.core.provenance import Provenance
from tidalist.nl.intent import parse_intent


def _intent():
    return {"name": "Winwood",
            "brief": {"criteria": [{"type": "performed_by", "artist": "Steve Winwood"}],
                      "ranking": {"type": "prefer_original"}},
            "candidates": [{"artist": "Traffic", "title": "Glad", "note": "signature"}]}


def test_parse_intent_returns_candidates_provenances_and_brief():
    candidates, provenances, brief = parse_intent(_intent())
    assert candidates == [Candidate("Traffic", "Glad")]
    assert provenances == [Provenance("nl", "signature")]
    assert brief.name == "Winwood"


def test_parse_intent_requires_a_name():
    bad = _intent()
    del bad["name"]
    with pytest.raises(ValueError):
        parse_intent(bad)


def test_parse_intent_requires_at_least_one_candidate():
    bad = _intent()
    bad["candidates"] = []
    with pytest.raises(ValueError):
        parse_intent(bad)


def test_parse_intent_rejects_an_unknown_criterion_type():
    bad = _intent()
    bad["brief"]["criteria"] = [{"type": "nope"}]
    with pytest.raises(ValueError):
        parse_intent(bad)


def test_parse_intent_source_is_overridable():
    _, provenances, _ = parse_intent(_intent(), source="scaruffi")
    assert provenances[0].source == "scaruffi"
