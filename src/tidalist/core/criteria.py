"""Hard admissibility rules (Specification pattern) and the Verdict they produce."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .album import Album
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
    def violation(self, item: "Album | Recording") -> str | None:
        """Reason the item fails this rule, or None if it passes."""
        ...


@dataclass(frozen=True, slots=True)
class PerformedBy:
    """Artist must be among the performers (not a cover). No-op on albums."""
    artist: str

    def violation(self, item: "Album | Recording") -> str | None:
        if not isinstance(item, Recording):
            return None
        if item.performs(self.artist):
            return None
        return f"{self.artist} not in performer credits (likely a cover)"


@dataclass(frozen=True, slots=True)
class Studio:
    """Recording must be a studio take, not live. No-op on albums."""

    def violation(self, item: "Album | Recording") -> str | None:
        if not isinstance(item, Recording):
            return None
        return "live recording" if item.is_live() else None


@dataclass(frozen=True, slots=True)
class NotCompilation:
    """Album must not be a compilation. No-op on recordings."""

    def violation(self, item: "Album | Recording") -> str | None:
        if isinstance(item, Album) and "Compilation" in item.secondary_types:
            return "compilation"
        return None


@dataclass(frozen=True, slots=True)
class NotLive:
    """Album must not be a live album. No-op on recordings."""

    def violation(self, item: "Album | Recording") -> str | None:
        if isinstance(item, Album) and "Live" in item.secondary_types:
            return "live album"
        return None
