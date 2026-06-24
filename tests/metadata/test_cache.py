"""CachingMusicBrainz: a persistent read-through cache around a musicbrainzngs client.

It memoizes the read methods to disk so the slow 1-req/s curate is resumable (a re-run
replays from disk) and recurring queries hit the network once; non-read methods delegate
straight through every time.
"""
from tidalist.metadata.cache import CachingMusicBrainz


class FakeMB:
    """A musicbrainzngs-like client that records every call and returns canned shapes."""

    def __init__(self):
        self.calls = []

    def search_artists(self, **kw):
        self.calls.append(("search_artists", kw))
        return {"artist-list": [{"id": "artist-mbid", "echo": kw}]}

    def search_release_groups(self, **kw):
        self.calls.append(("search_release_groups", kw))
        return {"release-group-list": [{"id": "rg-1", "echo": kw}]}

    def browse_releases(self, **kw):
        self.calls.append(("browse_releases", kw))
        return {"release-list": [{"id": "rel-1"}]}

    def set_useragent(self, *args, **kw):
        self.calls.append(("set_useragent", args, kw))

    def _count(self, method):
        return sum(1 for c in self.calls if c[0] == method)


def test_repeated_identical_read_hits_network_once(tmp_path):
    fake = FakeMB()
    mb = CachingMusicBrainz(fake, tmp_path)
    first = mb.search_artists(artist="Gardiner", limit=5)
    second = mb.search_artists(artist="Gardiner", limit=5)
    assert first == second == {"artist-list": [{"id": "artist-mbid",
                                                 "echo": {"artist": "Gardiner", "limit": 5}}]}
    assert fake._count("search_artists") == 1


def test_distinct_kwargs_are_distinct_entries(tmp_path):
    fake = FakeMB()
    mb = CachingMusicBrainz(fake, tmp_path)
    mb.search_artists(artist="Gardiner", limit=5)
    mb.search_artists(artist="Karajan", limit=5)
    assert fake._count("search_artists") == 2


def test_cache_persists_across_instances(tmp_path):
    cold = FakeMB()
    want = CachingMusicBrainz(cold, tmp_path).search_release_groups(
        artist="x", releasegroup="y", limit=25)
    warm = FakeMB()
    got = CachingMusicBrainz(warm, tmp_path).search_release_groups(
        artist="x", releasegroup="y", limit=25)
    assert got == want
    assert warm.calls == []  # served entirely from disk


def test_uncached_method_delegates_every_call(tmp_path):
    fake = FakeMB()
    mb = CachingMusicBrainz(fake, tmp_path)
    mb.set_useragent("tidalist", "1.0", "me@example.com")
    mb.set_useragent("tidalist", "1.0", "me@example.com")
    assert fake._count("set_useragent") == 2  # never cached


def test_atomic_write_leaves_no_temp_files(tmp_path):
    mb = CachingMusicBrainz(FakeMB(), tmp_path)
    mb.browse_releases(release_group="rg-1", limit=100)
    assert list(tmp_path.glob("**/*.tmp")) == []
    assert list(tmp_path.glob("**/*.json"))  # the response was persisted
