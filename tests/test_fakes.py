from tidalist.core.catalog import Track
from tidalist.core.identifiers import ISRC
from tests.fakes import FakeCatalog


def test_fake_catalog_finds_by_isrc():
    t = Track(id="1", title="Glad", artists=("Traffic",), isrc=ISRC("X"))
    assert FakeCatalog([t]).track_by_isrc(ISRC("X")) is t


def test_fake_catalog_search_matches_all_query_words():
    t = Track(id="1", title="Glad", artists=("Traffic",))
    assert FakeCatalog([t]).search_tracks("Traffic Glad") == [t]
    assert FakeCatalog([t]).search_tracks("Cream Glad") == []


def test_fake_catalog_create_and_add():
    cat = FakeCatalog([])
    pid = cat.create_playlist("p")
    cat.add_tracks(pid, ["1", "2"])
    assert cat.playlists[pid] == ["1", "2"]
