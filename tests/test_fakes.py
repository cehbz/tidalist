from tidalist.core.album import Album
from tidalist.core.catalog import Track
from tidalist.core.identifiers import ISRC
from tidalist.core.recording import Candidate
from tests.fakes import FakeCatalog, FakeMetadataProvider


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


def test_fake_metadata_provider_albums_for_returns_seeded_album():
    album = Album(artist="Talk Talk", title="Spirit of Eden")
    candidate = Candidate(artist="Talk Talk", title="Spirit of Eden")
    provider = FakeMetadataProvider(albums={"Spirit of Eden": [album]})
    assert provider.albums_for(candidate) == [album]


def test_fake_metadata_provider_albums_for_case_insensitive():
    album = Album(artist="Talk Talk", title="Spirit of Eden")
    candidate = Candidate(artist="Talk Talk", title="SPIRIT OF EDEN")
    provider = FakeMetadataProvider(albums={"Spirit of Eden": [album]})
    assert provider.albums_for(candidate) == [album]


def test_fake_metadata_provider_albums_for_unknown_returns_empty():
    provider = FakeMetadataProvider(albums={"Spirit of Eden": [Album(artist="Talk Talk", title="Spirit of Eden")]})
    assert provider.albums_for(Candidate(artist="Talk Talk", title="Laughing Stock")) == []


def test_fake_metadata_provider_recordings_positional_still_works():
    from tidalist.core.recording import Recording
    rec = Recording(title="Desire", artist="Talk Talk")
    candidate = Candidate(artist="Talk Talk", title="Desire")
    provider = FakeMetadataProvider({"Desire": rec})
    assert provider.recordings_for(candidate) == [rec]
