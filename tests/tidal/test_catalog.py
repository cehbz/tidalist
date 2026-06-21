from datetime import datetime
from types import SimpleNamespace

from tidalist.tidal.catalog import TidalCatalog


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


class _FakeSession:
    def __init__(self, tracks=(), isrc_hits=()):
        self._tracks = list(tracks)
        self._isrc_hits = list(isrc_hits)
        self.user = _FakeUser()
        self.pl = _FakePlaylist()
        self.searched = []

    def search(self, query, models=None, limit=50):
        self.searched.append((query, limit))
        return {"tracks": self._tracks}

    def get_tracks_by_isrc(self, isrc):
        return self._isrc_hits

    def playlist(self, pid):
        return self.pl


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
