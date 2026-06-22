"""Album: release-group identity value object."""

from dataclasses import dataclass

from .identifiers import MBID


@dataclass(frozen=True, slots=True)
class Album:
    """Release-group identity with edition type fields."""
    artist: str
    title: str
    mbid: MBID | None = None
    first_released: int | None = None
    primary_type: str | None = None
    secondary_types: tuple[str, ...] = ()
