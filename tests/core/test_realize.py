import pytest

from tidalist.core.recording import Recording
from tidalist.core.album import Album
from tidalist.core.criteria import Verdict
from tidalist.core.provenance import Provenance
from tidalist.core.brief import Brief
from tidalist.core.golden import GoldenEntry, GoldenPlaylist
from tidalist.core.realize import realize, publish, Realization, PlatformItem, MatchQuality, EditionOption, choose_edition
from tidalist.core.edition import EditionPreference
from tidalist.core.errors import CatalogError


class _FakeRealizer:
    """Resolves by recording title; a missing title is a gap. Records emit calls."""

    def __init__(self, items: dict):
        self._by_title = {k.casefold(): v for k, v in items.items()}
        self.emitted = []

    def resolve(self, recording):
        return self._by_title.get(recording.title.casefold())

    def emit(self, name, items):
        ref = f"playlist-{len(self.emitted) + 1}"
        self.emitted.append((name, [i.ref for i in items], ref))
        return ref


def _entry(title, admitted=True):
    rec = Recording(artist="Traffic", title=title)
    verdict = Verdict.ok() if admitted else Verdict.rejected("cover")
    return GoldenEntry(rec, Provenance("nl"), verdict)


def _golden(*entries, name="Winwood"):
    return GoldenPlaylist(name, Brief(name, ()), tuple(entries))


def _item(ref="t1", title="Glad"):
    return PlatformItem(ref=ref, title=title, artists=("Traffic",), quality=MatchQuality.ISRC)


def test_realize_resolves_each_admitted_entry():
    r = realize(_golden(_entry("Glad")), _FakeRealizer({"Glad": _item("T-glad")}))
    assert isinstance(r, Realization)
    assert len(r.entries) == 1
    assert r.entries[0].item.ref == "T-glad"


def test_realize_skips_rejected_golden_entries():
    golden = _golden(_entry("Glad"), _entry("Cover", admitted=False))
    r = realize(golden, _FakeRealizer({"Glad": _item("T-glad")}))
    assert [e.golden.item.title for e in r.entries] == ["Glad"]


def test_realize_records_a_gap_when_unresolved():
    golden = _golden(_entry("Glad"), _entry("Obscure"))
    r = realize(golden, _FakeRealizer({"Glad": _item("T-glad")}))   # Obscure unresolved
    assert [g.item.title for g in r.gaps()] == ["Obscure"]
    assert [e.golden.item.title for e in r.resolved()] == ["Glad"]


def test_publish_emits_only_resolved_items_and_returns_the_reference():
    golden = _golden(_entry("Glad"), _entry("Obscure"))
    realizer = _FakeRealizer({"Glad": _item("T-glad")})
    ref = publish(realize(golden, realizer), realizer)
    name, refs, returned = realizer.emitted[-1]
    assert name == "Winwood" and refs == ["T-glad"]
    assert ref == returned


def test_publish_raises_when_nothing_resolved():
    realizer = _FakeRealizer({})
    r = realize(_golden(_entry("Obscure")), realizer)
    with pytest.raises(CatalogError):
        publish(r, realizer)


def test_album_entry_is_a_gap_until_phase_5():
    g = _golden(GoldenEntry(Album(artist="Traffic", title="John Barleycorn Must Die"),
                            Provenance("nl"), Verdict.ok()))
    r = realize(g, _FakeRealizer({}))
    assert [e.item.title for e in r.gaps()] == ["John Barleycorn Must Die"]


# --- choose_edition tests ---

def test_choose_edition_empty_options_returns_none_none():
    chosen, compromise = choose_edition([], EditionPreference(markers=("steven wilson",)))
    assert chosen is None
    assert compromise is None


def test_choose_edition_marker_match_wins_no_compromise():
    options = [
        EditionOption(ref="orig", title="Close to the Edge", year=1972),
        EditionOption(ref="sw", title="Close to the Edge (Steven Wilson Mix)", year=2013),
    ]
    pref = EditionPreference(markers=("steven wilson",))
    chosen, compromise = choose_edition(options, pref)
    assert chosen is not None
    assert chosen.ref == "sw"
    assert compromise is None


def test_choose_edition_no_marker_falls_back_to_original_with_compromise():
    options = [
        EditionOption(ref="orig", title="Close to the Edge", year=1972),
        EditionOption(ref="remaster", title="Close to the Edge (Remastered)", year=2003),
    ]
    pref = EditionPreference(markers=("steven wilson",), prefer_original=True)
    chosen, compromise = choose_edition(options, pref)
    assert chosen is not None
    assert chosen.ref == "orig"
    assert compromise == "preferred edition (steven wilson) unavailable"


def test_choose_edition_no_marker_no_compromise_when_markers_empty():
    options = [
        EditionOption(ref="orig", title="Close to the Edge", year=1972),
        EditionOption(ref="remaster", title="Close to the Edge (Remastered)", year=2003),
    ]
    pref = EditionPreference(markers=(), prefer_original=True)
    chosen, compromise = choose_edition(options, pref)
    assert chosen is not None
    assert chosen.ref == "orig"
    assert compromise is None


def test_choose_edition_marker_order_honored_first_wins():
    options = [
        EditionOption(ref="mojo", title="Quadrophenia (MoFi Edition)", year=2011),
        EditionOption(ref="sw", title="Quadrophenia (Steven Wilson Mix)", year=2021),
    ]
    # "mobile fidelity" appears in title "MoFi Edition"? No, let's use exact markers.
    # First marker is "mobile fidelity" — won't match "MoFi". Use "mofi" to match.
    pref = EditionPreference(markers=("mofi", "steven wilson"))
    chosen, compromise = choose_edition(options, pref)
    assert chosen is not None
    assert chosen.ref == "mojo"
    assert compromise is None


def test_choose_edition_original_fallback_prefers_non_reissue_on_year_tie():
    options = [
        EditionOption(ref="deluxe", title="Thick as a Brick (Deluxe Edition)", year=1972),
        EditionOption(ref="orig", title="Thick as a Brick", year=1972),
    ]
    pref = EditionPreference(markers=(), prefer_original=True)
    chosen, compromise = choose_edition(options, pref)
    assert chosen is not None
    assert chosen.ref == "orig"


def test_choose_edition_none_year_sorts_last():
    options = [
        EditionOption(ref="no_year", title="Aqualung", year=None),
        EditionOption(ref="orig", title="Aqualung", year=1971),
    ]
    pref = EditionPreference(markers=(), prefer_original=True)
    chosen, compromise = choose_edition(options, pref)
    assert chosen is not None
    assert chosen.ref == "orig"
