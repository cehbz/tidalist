import json

import pytest

from tidalist.core.identifiers import ISRC, MBID
from tidalist.core.recording import Candidate, Credit, Recording, Performance, Kind
from tidalist.core.criteria import PerformedBy, Studio, Verdict
from tidalist.core.brief import Brief
from tidalist.core.provenance import Provenance
from tidalist.core.golden import GoldenPlaylist, GoldenEntry
from tidalist.core.spec import to_golden, from_golden, to_intent, from_intent


def test_unknown_criterion_type_raises():
    bad = {"name": "x", "brief": {"criteria": [{"type": "nope"}]}, "entries": []}
    with pytest.raises(ValueError):
        from_golden(bad)


# --- golden artifact ---------------------------------------------------------

def _golden():
    brief = Brief("Winwood", (PerformedBy("Steve Winwood"), Studio()))
    admitted = GoldenEntry(
        Recording(artist="Traffic", title="Glad", mbid=MBID("rec-1"),
                  isrc=ISRC("GBABC1234567"), album="John Barleycorn Must Die",
                  first_released=1970, duration_s=386, performance=Performance.STUDIO,
                  credits=(Credit("Steve Winwood", "performer"),)),
        Provenance("nl", "signature track"), Verdict.ok())
    gap = GoldenEntry(Recording(artist="Nobody", title="Nothing"),
                      Provenance("nl"), Verdict.rejected("no recording found"))
    return GoldenPlaylist("Winwood", brief, (admitted, gap))


def test_golden_round_trips():
    golden = _golden()
    assert from_golden(to_golden(golden)) == golden


def test_golden_is_pure_json():
    spec = to_golden(_golden())
    assert json.loads(json.dumps(spec)) == spec


def test_golden_entry_flattens_recording_fields_with_year_key():
    entry = to_golden(_golden())["entries"][0]
    assert entry["mbid"] == "rec-1" and entry["year"] == 1970
    assert entry["artist"] == "Traffic" and entry["title"] == "Glad"
    assert entry["provenance"]["note"] == "signature track"
    assert entry["verdict"]["admitted"] is True


# --- intent artifact (the front-end hand-off: candidates + notes + brief) -----

def _intent():
    brief = Brief("Winwood", (PerformedBy("Steve Winwood"), Studio()))
    candidates = [Candidate("Traffic", "Glad", album="John Barleycorn Must Die", year=1970),
                  Candidate("Blind Faith", "Presence of the Lord")]
    provenances = [Provenance("nl", "signature Traffic track"),
                   Provenance("nl", "supergroup peak")]
    return brief, candidates, provenances


def test_intent_round_trips():
    brief, candidates, provenances = _intent()
    c2, p2, b2 = from_intent(to_intent(brief, candidates, provenances))
    assert c2 == candidates and p2 == provenances and b2 == brief


def test_intent_is_pure_json():
    brief, candidates, provenances = _intent()
    spec = to_intent(brief, candidates, provenances)
    assert json.loads(json.dumps(spec)) == spec


def test_from_intent_attaches_per_candidate_note_as_provenance():
    data = {"name": "x", "brief": {"criteria": []},
            "candidates": [{"artist": "A", "title": "T", "note": "because"}]}
    candidates, provenances, _ = from_intent(data)
    assert candidates[0] == Candidate("A", "T")
    assert provenances[0] == Provenance("nl", "because")


def test_from_intent_source_defaults_to_nl_and_is_overridable():
    data = {"name": "x", "brief": {"criteria": []},
            "candidates": [{"artist": "A", "title": "T"}]}
    assert from_intent(data)[1][0].source == "nl"
    assert from_intent(data, source="scaruffi")[1][0].source == "scaruffi"


def test_intent_round_trips_candidate_kind():
    brief = Brief("x", ())
    candidates = [Candidate("Traffic", "John Barleycorn Must Die", kind=Kind.ALBUM),
                  Candidate("Spencer Davis Group", "Gimme Some Lovin'")]  # default TRACK
    provenances = [Provenance("nl", "album"), Provenance("nl", "track")]
    c2, _, _ = from_intent(to_intent(brief, candidates, provenances))
    assert [c.kind for c in c2] == [Kind.ALBUM, Kind.TRACK]
