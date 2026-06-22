import json

import pytest

from tidalist.core.identifiers import ISRC, MBID
from tidalist.core.recording import Candidate, Credit, Recording, Performance, Kind
from tidalist.core.album import Album
from tidalist.core.criteria import PerformedBy, Studio, NotCompilation, NotLive, Verdict
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


def test_golden_round_trips_album_and_track_entries():
    brief = Brief("Winwood", ())
    track = GoldenEntry(Recording(artist="Traffic", title="Glad", mbid=MBID("r1"),
                                  first_released=1970, performance=Performance.STUDIO),
                        Provenance("nl"), Verdict.ok())
    album = GoldenEntry(Album(artist="Traffic", title="John Barleycorn Must Die",
                              mbid=MBID("rg1"), first_released=1970),
                        Provenance("nl", "whole album"), Verdict.ok())
    g = GoldenPlaylist("Winwood", brief, (track, album))
    assert from_golden(to_golden(g)) == g
    dicts = to_golden(g)["entries"]
    assert dicts[0]["kind"] == "track" and dicts[1]["kind"] == "album"
    assert dicts[1]["mbid"] == "rg1"


def test_intent_round_trips_candidate_kind():
    brief = Brief("x", ())
    candidates = [Candidate("Traffic", "John Barleycorn Must Die", kind=Kind.ALBUM),
                  Candidate("Spencer Davis Group", "Gimme Some Lovin'")]  # default TRACK
    provenances = [Provenance("nl", "album"), Provenance("nl", "track")]
    c2, _, _ = from_intent(to_intent(brief, candidates, provenances))
    assert [c.kind for c in c2] == [Kind.ALBUM, Kind.TRACK]


# --- Phase 4 Task 1: new criteria serialization ---

def test_not_compilation_round_trips():
    brief = Brief("x", (NotCompilation(),))
    d = {"name": "x", "brief": {"criteria": [{"type": "not_compilation"}]}, "entries": []}
    g = from_golden(d)
    assert g.brief.criteria[0] == NotCompilation()


def test_not_live_round_trips():
    brief = Brief("x", (NotLive(),))
    d = {"name": "x", "brief": {"criteria": [{"type": "not_live"}]}, "entries": []}
    g = from_golden(d)
    assert g.brief.criteria[0] == NotLive()


def test_not_compilation_serializes_to_expected_dict():
    from tidalist.core.spec import _criterion_to_dict
    assert _criterion_to_dict(NotCompilation()) == {"type": "not_compilation"}


def test_not_live_serializes_to_expected_dict():
    from tidalist.core.spec import _criterion_to_dict
    assert _criterion_to_dict(NotLive()) == {"type": "not_live"}


# --- Phase 4 Task 1: album golden entry carries type fields ---

def test_golden_album_entry_round_trips_with_type_fields():
    brief = Brief("Winwood", ())
    album = Album(artist="Traffic", title="John Barleycorn Must Die",
                  mbid=MBID("rg1"), first_released=1970,
                  primary_type="Album", secondary_types=("Live",))
    entry = GoldenEntry(album, Provenance("nl"), Verdict.ok())
    g = GoldenPlaylist("Winwood", brief, (entry,))
    result = from_golden(to_golden(g))
    a = result.entries[0].item
    assert isinstance(a, Album)
    assert a.primary_type == "Album"
    assert a.secondary_types == ("Live",)


def test_golden_album_entry_serializes_type_fields():
    from tidalist.core.spec import _golden_entry_to_dict
    from tidalist.core.provenance import Provenance
    from tidalist.core.golden import GoldenEntry
    album = Album(artist="Traffic", title="John Barleycorn Must Die",
                  primary_type="Album", secondary_types=("Compilation",))
    entry = GoldenEntry(album, Provenance("nl"), Verdict.ok())
    d = _golden_entry_to_dict(entry)
    assert d["primary_type"] == "Album"
    assert d["secondary_types"] == ["Compilation"]
