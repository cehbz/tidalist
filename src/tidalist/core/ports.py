"""Outbound ports; adapters implement them structurally."""

from typing import Protocol, runtime_checkable

from .album import Album
from .identifiers import ISRC, TrackId, PlaylistId
from .catalog import Track
from .recording import Candidate, Recording


@runtime_checkable
class Catalog(Protocol):
    def search_tracks(self, query: str, limit: int = 25) -> list[Track]: ...
    def track_by_isrc(self, isrc: ISRC) -> Track | None: ...
    def create_playlist(self, name: str, description: str = "") -> PlaylistId: ...
    def add_tracks(self, playlist: PlaylistId, tracks: list[TrackId]) -> None: ...


@runtime_checkable
class MetadataProvider(Protocol):
    def recordings_for(self, candidate: Candidate) -> list[Recording]: ...
    def albums_for(self, candidate: Candidate) -> list[Album]: ...
