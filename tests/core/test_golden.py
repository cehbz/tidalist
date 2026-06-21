import pytest

from tidalist.core.recording import Candidate, Credit, Recording, Performance
from tidalist.core.criteria import PerformedBy, Studio
from tidalist.core.ranking import PreferOriginal
from tidalist.core.brief import Brief
from tidalist.core.provenance import Provenance
from tidalist.core.golden import Curator, GoldenPlaylist, GoldenEntry
from tests.fakes import FakeMetadataProvider


def _rec(title="Glad", artist="Traffic", performer="Steve Winwood",
         performance=Performance.STUDIO, year=1970, mbid="mb-1"):
    return Recording(artist=artist, title=title, mbid=mbid, performance=performance,
                     first_released=year, credits=(Credit(performer, "performer"),))


def _brief(*criteria):
    return Brief("Winwood", tuple(criteria), PreferOriginal())


def _curate(meta_map, brief, candidates, provenances=None):
    return Curator(FakeMetadataProvider(meta_map)).curate(brief, candidates, provenances)


def test_curate_builds_a_golden_playlist_named_for_the_brief():
    golden = _curate({"Glad": _rec()}, _brief(), [Candidate("Traffic", "Glad")])
    assert isinstance(golden, GoldenPlaylist)
    assert golden.name == "Winwood"
    assert golden.brief == _brief()
    assert len(golden.entries) == 1
    assert isinstance(golden.entries[0], GoldenEntry)


def test_curate_admits_a_recording_that_satisfies_the_criteria():
    golden = _curate({"Glad": _rec()}, _brief(PerformedBy("Steve Winwood")),
                     [Candidate("Traffic", "Glad")])
    entry = golden.entries[0]
    assert entry.recording.title == "Glad"
    assert entry.verdict.admitted


def test_curate_rejects_a_cover_but_keeps_the_entry_with_reasons():
    cover = _rec(title="Feelin Alright", artist="Joe Cocker", performer="Joe Cocker")
    golden = _curate({"Feelin Alright": cover}, _brief(PerformedBy("Steve Winwood")),
                     [Candidate("Joe Cocker", "Feelin Alright")])
    entry = golden.entries[0]
    assert not entry.verdict.admitted
    assert any("cover" in v for v in entry.verdict.violations)


def test_curate_picks_the_studio_take_over_a_live_one():
    studio = _rec(performance=Performance.STUDIO, year=1970, mbid="s")
    live = _rec(performance=Performance.LIVE, year=1973, mbid="l")
    golden = _curate({"Glad": [live, studio]}, _brief(), [Candidate("Traffic", "Glad")])
    assert golden.entries[0].recording.mbid == "s"
    assert golden.entries[0].recording.performance is Performance.STUDIO


def test_curate_chooses_among_admissible_under_a_studio_criterion():
    studio = _rec(performance=Performance.STUDIO, mbid="s")
    live = _rec(performance=Performance.LIVE, mbid="l")
    golden = _curate({"Glad": [live, studio]}, _brief(Studio()), [Candidate("Traffic", "Glad")])
    entry = golden.entries[0]
    assert entry.recording.mbid == "s" and entry.verdict.admitted


def test_curate_surfaces_a_best_effort_recording_when_none_admissible():
    live = _rec(performance=Performance.LIVE, mbid="l")
    golden = _curate({"Glad": [live]}, _brief(Studio()), [Candidate("Traffic", "Glad")])
    entry = golden.entries[0]
    assert entry.recording.mbid == "l"          # surfaced for review
    assert not entry.verdict.admitted
    assert any("live" in v for v in entry.verdict.violations)


def test_curate_reports_a_gap_when_no_recording_is_found():
    golden = _curate({}, _brief(), [Candidate("Nobody", "Nothing")])
    entry = golden.entries[0]
    assert entry.recording.artist == "Nobody" and entry.recording.title == "Nothing"
    assert entry.recording.mbid is None
    assert not entry.verdict.admitted
    assert any("no recording" in v.lower() for v in entry.verdict.violations)


def test_curate_defaults_provenance_to_nl():
    golden = _curate({"Glad": _rec()}, _brief(), [Candidate("Traffic", "Glad")])
    assert golden.entries[0].provenance == Provenance("nl")


def test_curate_carries_per_candidate_provenance_including_notes():
    golden = _curate(
        {"A": _rec(title="A"), "B": _rec(title="B")}, _brief(),
        [Candidate("x", "A"), Candidate("x", "B")],
        provenances=[Provenance("scaruffi", "first"), Provenance("nl", "second")])
    assert [(e.provenance.source, e.provenance.note) for e in golden.entries] \
        == [("scaruffi", "first"), ("nl", "second")]


def test_curate_rejects_provenances_of_mismatched_length():
    with pytest.raises(ValueError):
        _curate({"A": _rec(title="A")}, _brief(), [Candidate("x", "A")],
                provenances=[Provenance("nl"), Provenance("nl")])


def test_curate_preserves_candidate_order():
    golden = _curate({"A": _rec(title="A"), "B": _rec(title="B")}, _brief(),
                     [Candidate("x", "B"), Candidate("x", "A")])
    assert [e.recording.title for e in golden.entries] == ["B", "A"]
