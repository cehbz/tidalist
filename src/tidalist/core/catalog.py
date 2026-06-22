"""Catalog value objects: a playable Track and a platform album descriptor."""

from dataclasses import dataclass
from enum import StrEnum

from .identifiers import ISRC, TrackId


class Edition(StrEnum):
    """How a release presents a recording. A Track property, distinct from Performance."""
    ORIGINAL = "original"
    COMPILATION = "compilation"
    SINGLE = "single"
    REISSUE = "reissue"
    LIVE = "live"          # live-album release (cf. Performance.LIVE)
    SOUNDTRACK = "soundtrack"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Track:
    id: TrackId
    title: str
    artists: tuple[str, ...]
    isrc: ISRC | None = None
    album: str | None = None
    year: int | None = None
    edition: Edition = Edition.UNKNOWN
    duration_s: int | None = None

    def __post_init__(self):
        if self.year is not None and not isinstance(self.year, int):
            raise TypeError(f"Track.year must be int | None, got {type(self.year).__name__}")
        if not self.artists:
            raise ValueError("Track requires at least one artist")

    @property
    def primary_artist(self) -> str:
        return self.artists[0]


@dataclass(frozen=True, slots=True)
class CatalogAlbum:
    """A platform album descriptor returned by Catalog.search_albums."""
    id: TrackId
    title: str
    artists: tuple[str, ...]
    year: int | None = None
    num_tracks: int | None = None

