"""Platform value objects: a playable Track and a platform album descriptor."""

from dataclasses import dataclass

from .identifiers import ISRC, TrackId


@dataclass(frozen=True, slots=True)
class Track:
    id: TrackId
    title: str
    artists: tuple[str, ...]
    isrc: ISRC | None = None
    album: str | None = None
    year: int | None = None
    duration_s: int | None = None
    audio_quality: str | None = None
    popularity: int | None = None

    def __post_init__(self):
        if self.year is not None and not isinstance(self.year, int):
            raise TypeError(f"Track.year must be int | None, got {type(self.year).__name__}")
        if not self.artists:
            raise ValueError("Track requires at least one artist")

    @property
    def primary_artist(self) -> str:
        return self.artists[0]


@dataclass(frozen=True, slots=True)
class PlatformAlbum:
    """A platform album descriptor returned by Platform.search_albums."""
    id: TrackId
    title: str
    artists: tuple[str, ...]
    year: int | None = None
    num_tracks: int | None = None

