"""In-memory implementations of the Catalog and MetadataProvider ports for tests.

These are real (deterministic) implementations, not mocks — tests specify behavior
against them, not against call expectations.
"""

from tidalist.core.identifiers import PlaylistId
from tidalist.core.catalog import Track
from tidalist.core.recording import Candidate, Recording


class FakeCatalog:
    def __init__(self, tracks):
        self._tracks = list(tracks)
        self.playlists: dict[str, list] = {}
        self._n = 0

    @staticmethod
    def _haystack(t: Track) -> str:
        return f"{t.title} {' '.join(t.artists)} {t.album or ''}".casefold()

    def search_tracks(self, query: str, limit: int = 25) -> list[Track]:
        words = query.casefold().split()
        return [t for t in self._tracks
                if all(w in self._haystack(t) for w in words)][:limit]

    def track_by_isrc(self, isrc):
        return next((t for t in self._tracks if t.isrc == isrc), None)

    def create_playlist(self, name: str, description: str = "") -> PlaylistId:
        self._n += 1
        pid = PlaylistId(f"pl-{self._n}")
        self.playlists[pid] = []
        return pid

    def add_tracks(self, playlist, tracks) -> None:
        self.playlists[playlist].extend(tracks)


class FakeMetadataProvider:
    def __init__(self, recordings: dict[str, Recording | list[Recording]]):
        # keyed by candidate title (case-insensitive); value is a Recording or a list.
        self._by_title = {k.casefold(): (list(v) if isinstance(v, list) else [v])
                          for k, v in recordings.items()}

    def recordings_for(self, candidate: Candidate) -> list[Recording]:
        return list(self._by_title.get(candidate.title.casefold(), []))


class FakeRealizer:
    """Realizer port fake: resolves by recording title (missing => gap); records emits."""

    def __init__(self, items: dict):
        self._by_title = {k.casefold(): v for k, v in items.items()}
        self.emitted: list = []

    def resolve(self, recording):
        return self._by_title.get(recording.title.casefold())

    def emit(self, name: str, items: list) -> str:
        ref = f"playlist-{len(self.emitted) + 1}"
        self.emitted.append((name, [i.ref for i in items], ref))
        return ref
