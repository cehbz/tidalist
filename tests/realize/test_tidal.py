from tidalist.core.identifiers import ISRC, TrackId
from tidalist.core.recording import Recording, Credit
from tidalist.core.catalog import Track, CatalogAlbum
from tidalist.core.album import Album
from tidalist.core.edition import EditionPreference, EditionPolicy
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


# --- resolve_album tests ---

def _album(id="A1", title="John Barleycorn Must Die", artists=("Traffic",), year=1970):
    return CatalogAlbum(id=TrackId(id), title=title, artists=artists, year=year)


def _album_track(id, title, artists=("Traffic",)):
    return Track(id=TrackId(id), title=title, artists=artists)


def _domain_album(artist="Traffic", title="John Barleycorn Must Die"):
    return Album(artist=artist, title=title)


def test_resolve_album_drops_wrong_artist():
    wrong_artist = _album(id="A-wrong", title="John Barleycorn Must Die",
                          artists=("Some Other Band",))
    cat = FakeCatalog(
        [],
        albums=[wrong_artist],
        album_track_map={"A-wrong": [_album_track("T1", "Glad")]},
    )
    items, compromise = TidalRealizer(cat).resolve_album(
        _domain_album(), EditionPolicy.default()
    )
    assert items == []
    assert compromise is None


def test_resolve_album_picks_original_over_deluxe():
    original = _album(id="A-orig", title="John Barleycorn Must Die", year=1970)
    deluxe = _album(id="A-deluxe", title="John Barleycorn Must Die (Deluxe Edition)", year=2004)
    tracks = [
        _album_track("T1", "Glad"),
        _album_track("T2", "Freedom Rider"),
    ]
    cat = FakeCatalog(
        [],
        albums=[deluxe, original],
        album_track_map={"A-orig": tracks, "A-deluxe": tracks[:1]},
    )
    items, compromise = TidalRealizer(cat).resolve_album(
        _domain_album(), EditionPolicy.default()
    )
    assert [i.ref for i in items] == ["T1", "T2"]
    assert all(i.quality is MatchQuality.STRONG for i in items)


def test_resolve_album_returns_tracks_in_order():
    album = _album(id="A1")
    ordered_tracks = [
        _album_track("T1", "Glad"),
        _album_track("T2", "Freedom Rider"),
        _album_track("T3", "Empty Pages"),
    ]
    cat = FakeCatalog(
        [],
        albums=[album],
        album_track_map={"A1": ordered_tracks},
    )
    items, _ = TidalRealizer(cat).resolve_album(_domain_album(), EditionPolicy.default())
    assert [i.ref for i in items] == ["T1", "T2", "T3"]


def test_resolve_album_returns_empty_when_nothing_matches():
    cat = FakeCatalog([], albums=[], album_track_map={})
    items, compromise = TidalRealizer(cat).resolve_album(
        _domain_album(), EditionPolicy.default()
    )
    assert items == []
    assert compromise is None
