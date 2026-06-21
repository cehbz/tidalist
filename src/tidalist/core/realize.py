"""The realize stage: map a golden playlist onto one platform, best-effort.

A `Realizer` resolves a recording to a platform item (ISRC-first, then closeness) and
emits a playlist. `realize` resolves every admitted golden entry into a `Realization`
(resolved items + gaps) without writing; `publish` then emits the resolved items. The
two are separate so gaps can be reviewed before anything is created on the platform.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from .identifiers import ISRC
from .recording import Recording
from .golden import GoldenEntry, GoldenPlaylist
from .errors import CatalogError


class MatchQuality(StrEnum):
    """How confidently a recording was matched to a platform item."""
    ISRC = "isrc"        # exact: same recording by ISRC
    STRONG = "strong"    # title and artist agree
    WEAK = "weak"        # found something, low confidence


@dataclass(frozen=True, slots=True)
class PlatformItem:
    """A resolved playable item: `ref` is the token `emit` needs (a track id, a path)."""
    ref: str
    title: str
    artists: tuple[str, ...]
    isrc: ISRC | None = None
    quality: MatchQuality = MatchQuality.WEAK


@dataclass(frozen=True, slots=True)
class RealizedEntry:
    golden: GoldenEntry
    item: PlatformItem | None    # None = gap (no platform match)

    @property
    def is_gap(self) -> bool:
        return self.item is None


@dataclass(frozen=True, slots=True)
class Realization:
    name: str
    entries: tuple[RealizedEntry, ...]

    def resolved(self) -> tuple[RealizedEntry, ...]:
        return tuple(e for e in self.entries if not e.is_gap)

    def gaps(self) -> tuple[GoldenEntry, ...]:
        return tuple(e.golden for e in self.entries if e.is_gap)


@runtime_checkable
class Realizer(Protocol):
    def resolve(self, recording: Recording) -> PlatformItem | None: ...
    def emit(self, name: str, items: list[PlatformItem]) -> str: ...


def realize(golden: GoldenPlaylist, realizer: Realizer) -> Realization:
    """Resolve every admitted golden entry to a platform item (or a gap). No writes."""
    entries = tuple(
        RealizedEntry(e, realizer.resolve(e.item) if isinstance(e.item, Recording) else None)
        for e in golden.entries if e.verdict.admitted
    )
    return Realization(golden.name, entries)


def publish(realization: Realization, realizer: Realizer) -> str:
    """Emit the resolved items to the platform; return the platform playlist reference."""
    items = [e.item for e in realization.resolved()]
    if not items:
        raise CatalogError(f"nothing resolved to publish for '{realization.name}'")
    return realizer.emit(realization.name, items)
