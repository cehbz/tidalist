"""Hard admissibility rules (Specification pattern) and the Verdict they produce."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .recording import Recording


@dataclass(frozen=True, slots=True)
class Verdict:
    admitted: bool
    violations: tuple[str, ...] = ()

    @classmethod
    def ok(cls) -> "Verdict":
        return cls(True, ())

    @classmethod
    def rejected(cls, *reasons: str) -> "Verdict":
        return cls(False, tuple(reasons))


@runtime_checkable
class Criterion(Protocol):
    def violation(self, recording: Recording) -> str | None:
        """Reason the recording fails this rule, or None if it passes."""
        ...


@dataclass(frozen=True, slots=True)
class PerformedBy:
    """Artist must be among the performers (not a cover)."""
    artist: str

    def violation(self, recording: Recording) -> str | None:
        if recording.performs(self.artist):
            return None
        return f"{self.artist} not in performer credits (likely a cover)"


@dataclass(frozen=True, slots=True)
class Studio:
    """Recording must be a studio take, not live."""

    def violation(self, recording: Recording) -> str | None:
        return "live recording" if recording.is_live() else None
