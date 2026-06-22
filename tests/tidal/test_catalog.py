from datetime import datetime
from types import SimpleNamespace

from tidalist.tidal.catalog import TidalCatalog
from tidalist.core.catalog import CatalogAlbum


def _track(id, title="t", artist="a"):
    return SimpleNamespace(id=id, name=title, artists=[SimpleNamespace(name=artist)],
                           isrc=None, album=SimpleNamespace(name="A", year=1970),
                           tidal_release_date=datetime(1970, 1, 1), duration=100)


class _FakeUser:
    def __init__(self):
        self.created = []

    def create_playlist(self, title, description):
        self.created.append((title, description))
        return SimpleNamespace(id="PL1")


class _FakePlaylist:
    def __init__(self):
        self.added = []

    def add(self, ids):
        self.added.append(ids)


def _tidal_album(id, name="John Barleycorn Must Die", artist="Traffic", year=1970, num_tracks=6):
    return SimpleNamespace(
        id=id,
        name=name,
        artists=[SimpleNamespace(name=artist)],
        year=year,
        num_tracks=num_tracks,
    )


class _FakeAlbumObj:
    """Represents what session.album(id) returns — has a .tracks() method."""
    def __init__(self, tracks):
        self._tracks = tracks

    def tracks(self):
        return self._tracks


class _FakeSession:
    def __init__(self, tracks=(), isrc_hits=(), albums=(), album_tracks_map=None):
        self._tracks = list(tracks)
        self._isrc_hits = list(isrc_hits)
        self._albums = list(albums)
        self._album_tracks_map = album_tracks_map or {}
        self.user = _FakeUser()
        self.pl = _FakePlaylist()
        self.searched = []

    def search(self, query, models=None, limit=50):
        self.searched.append((query, limit))
        if models and hasattr(models[0], "__name__") and models[0].__name__ == "Album":
            return {"albums": self._albums}
        return {"tracks": self._tracks}

    def get_tracks_by_isrc(self, isrc):
        return self._isrc_hits

    def playlist(self, pid):
        return self.pl

    def album(self, album_id):
        return _FakeAlbumObj(self._album_tracks_map.get(str(album_id), []))


def test_search_tracks_maps_and_limits():
    session = _FakeSession(tracks=[_track(1, "Glad"), _track(2, "Empty Pages")])
    out = TidalCatalog(session).search_tracks("Traffic", limit=1)
    assert [t.title for t in out] == ["Glad"]
    assert session.searched == [("Traffic", 1)]


def test_track_by_isrc_returns_first_hit_mapped():
    session = _FakeSession(isrc_hits=[_track(9, "Glad")])
    t = TidalCatalog(session).track_by_isrc("GBABC1234567")
    assert t.id == "9" and t.title == "Glad"


def test_track_by_isrc_none_when_no_hit():
    assert TidalCatalog(_FakeSession()).track_by_isrc("ZZ") is None


def test_create_playlist_returns_id():
    session = _FakeSession()
    pid = TidalCatalog(session).create_playlist("Winwood", "desc")
    assert pid == "PL1"
    assert session.user.created == [("Winwood", "desc")]


def test_add_tracks_passes_string_ids():
    session = _FakeSession()
    TidalCatalog(session).add_tracks("PL1", ["1", "2"])
    assert session.pl.added == [["1", "2"]]


def test_search_albums_maps_to_catalog_album():
    ta = _tidal_album(42, name="John Barleycorn Must Die", artist="Traffic", year=1970, num_tracks=6)
    session = _FakeSession(albums=[ta])
    results = TidalCatalog(session).search_albums("Traffic John Barleycorn Must Die", limit=5)
    assert len(results) == 1
    a = results[0]
    assert isinstance(a, CatalogAlbum)
    assert a.id == "42"
    assert a.title == "John Barleycorn Must Die"
    assert a.artists == ("Traffic",)
    assert a.year == 1970
    assert a.num_tracks == 6
    assert session.searched == [("Traffic John Barleycorn Must Die", 5)]


def test_search_albums_limits_results():
    albums = [_tidal_album(i) for i in range(5)]
    session = _FakeSession(albums=albums)
    results = TidalCatalog(session).search_albums("Traffic", limit=2)
    assert len(results) == 2


def test_album_tracks_returns_mapped_tracks():
    t1 = _track(1, "Glad")
    t2 = _track(2, "Freedom Rider")
    session = _FakeSession(album_tracks_map={"99": [t1, t2]})
    tracks = TidalCatalog(session).album_tracks("99")
    assert [t.title for t in tracks] == ["Glad", "Freedom Rider"]
    assert [t.id for t in tracks] == ["1", "2"]


def test_album_tracks_returns_empty_for_unknown_id():
    session = _FakeSession()
    assert TidalCatalog(session).album_tracks("nonexistent") == []
