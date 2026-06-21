import pytest

from tidalist.core.recording import Recording
from tidalist.core.album import Album
from tidalist.core.criteria import Verdict
from tidalist.core.provenance import Provenance
from tidalist.core.brief import Brief
from tidalist.core.golden import GoldenEntry, GoldenPlaylist
from tidalist.core.realize import realize, publish, Realization, PlatformItem, MatchQuality
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
