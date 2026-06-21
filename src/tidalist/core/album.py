"""Album: release-group identity value object."""

from dataclasses import dataclass

from .identifiers import MBID


@dataclass(frozen=True, slots=True)
class Album:
    """Release-group identity. Edition fields arrive in Phase 4 — do not add them here."""
    artist: str
    title: str
    mbid: MBID | None = None
    first_released: int | None = None
