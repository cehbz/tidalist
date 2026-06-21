"""Soft ordering for under-specified candidates: a tiebreaker applied after ISRC and album-pin matches."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .recording import Recording
from .catalog import Edition, Track


@runtime_checkable
class Ranking(Protocol):
    def key(self, recording: Recording | None, track: Track) -> tuple:
        """Edition/realize sort key over a resolved track; lower first."""
        ...


@runtime_checkable
class RecordingRanking(Protocol):
    def key(self, recording: Recording) -> tuple:
        """Golden-stage sort key over a recording alone (no track); lower first."""
        ...


@dataclass(frozen=True, slots=True)
class PreferStudioEarliest:
    """Golden recording-ranking: prefer studio over live, then earliest release."""

    def key(self, recording: Recording) -> tuple:
        live = 1 if recording.is_live() else 0
        year = recording.first_released if recording.first_released is not None else 9999
        return (live, year)


# Lower sorts first.
_EDITION_PENALTY = {
    Edition.ORIGINAL: 0,
    Edition.SINGLE: 0,
    Edition.UNKNOWN: 1,
    Edition.SOUNDTRACK: 2,
    Edition.REISSUE: 3,
    Edition.LIVE: 3,
    Edition.COMPILATION: 3,
}


@dataclass(frozen=True, slots=True)
class PreferOriginal:
    """Prefer original studio edition, earliest year."""

    def key(self, recording: Recording | None, track: Track) -> tuple:
        live = 1 if (recording is not None and recording.is_live()) else 0
        edition = _EDITION_PENALTY.get(track.edition, 1)
        year = (recording.first_released if recording and recording.first_released is not None
                else track.year if track.year is not None else 9999)
        return (live, edition, year)
