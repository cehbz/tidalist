from tidalist.core.identifiers import ISRC, TrackId
from tidalist.core.recording import Recording, Credit
from tidalist.core.catalog import Track
from tidalist.core.realize import MatchQuality, PlatformItem
from tidalist.realize.tidal import TidalRealizer
from tests.fakes import FakeCatalog


def _rec(title="Glad", artist="Traffic", isrc=None, album=None, duration_s=None,
         performer="Steve Winwood"):
    return Recording(artist=artist, title=title, isrc=isrc, album=album,
                     duration_s=duration_s, credits=(Credit(performer, "performer"),))


def _track(id, title="Glad", artists=("Traffic",), isrc=None, album=None, duration_s=None):
    return Track(id=TrackId(id), title=title, artists=artists, isrc=isrc, album=album,
                 duration_s=duration_s)


def test_resolve_by_isrc_takes_precedence_with_isrc_quality():
    target = _track("T-isrc", isrc=ISRC("GB1"))
    cat = FakeCatalog([target, _track("T-decoy")])
    item = TidalRealizer(cat).resolve(_rec(isrc=ISRC("GB1")))
    assert item.ref == "T-isrc" and item.quality is MatchQuality.ISRC


def test_resolve_falls_back_to_closest_search_hit():
    right = _track("T-right", title="Glad", artists=("Traffic",))
    looser = _track("T-loose", title="Glad Rag Doll", artists=("Traffic",))
    cat = FakeCatalog([looser, right])
    item = TidalRealizer(cat).resolve(_rec())
    assert item.ref == "T-right" and item.quality is MatchQuality.STRONG


def test_resolve_returns_none_when_search_finds_nothing():
    assert TidalRealizer(FakeCatalog([])).resolve(_rec()) is None


def test_resolve_prefers_closer_duration_among_equal_hits():
    a = _track("T-a", title="Glad", artists=("Traffic",), duration_s=200)
    b = _track("T-b", title="Glad", artists=("Traffic",), duration_s=386)
    cat = FakeCatalog([a, b])
    assert TidalRealizer(cat).resolve(_rec(duration_s=386)).ref == "T-b"


def test_resolve_marks_a_title_mismatch_weak():
    only = _track("T-x", title="Glad Rag Doll", artists=("Traffic",))
    item = TidalRealizer(FakeCatalog([only])).resolve(_rec())
    assert item.ref == "T-x" and item.quality is MatchQuality.WEAK


def test_emit_creates_a_playlist_and_adds_the_item_refs():
    cat = FakeCatalog([])
    items = [PlatformItem(ref="T1", title="Glad", artists=("Traffic",)),
             PlatformItem(ref="T2", title="Dear Mr Fantasy", artists=("Traffic",))]
    ref = TidalRealizer(cat).emit("Winwood", items)
    assert cat.playlists[ref] == ["T1", "T2"]
