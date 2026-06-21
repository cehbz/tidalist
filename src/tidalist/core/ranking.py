"""Recording-ranking: soft ordering over recordings, for golden discrimination."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .recording import Recording


@runtime_checkable
class RecordingRanking(Protocol):
    def key(self, recording: Recording) -> tuple:
        """Sort key over a recording alone; lower first."""
        ...


@dataclass(frozen=True, slots=True)
class PreferStudioEarliest:
    """Prefer studio over live, then earliest release."""

    def key(self, recording: Recording) -> tuple:
        live = 1 if recording.is_live() else 0
        year = recording.first_released if recording.first_released is not None else 9999
        return (live, year)
