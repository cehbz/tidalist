"""Album: release-group identity value object."""

from dataclasses import dataclass

from .identifiers import ISRC, MBID


@dataclass(frozen=True, slots=True)
class TrackRef:
    """One track of an album's canonical tracklist: ordered identity for edition distance."""
    position: int
    title: str
    isrc: ISRC | None = None
    mbid: MBID | None = None
    duration_s: int | None = None


@dataclass(frozen=True, slots=True)
class Album:
    """Release-group identity with edition type fields."""
    artist: str
    title: str
    mbid: MBID | None = None
    first_released: int | None = None
    primary_type: str | None = None
    secondary_types: tuple[str, ...] = ()
    tracklist: tuple[TrackRef, ...] = ()
