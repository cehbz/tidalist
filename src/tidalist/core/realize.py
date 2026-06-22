"""The realize stage: map a golden playlist onto one platform, best-effort.

A `Realizer` resolves a recording to a platform item (ISRC-first, then closeness) and
emits a playlist. `realize` resolves every admitted golden entry into a `Realization`
(resolved items + gaps) without writing; `publish` then emits the resolved items. The
two are separate so gaps can be reviewed before anything is created on the platform.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from .edition import EditionPreference
from .identifiers import ISRC
from .recording import Recording
from .golden import GoldenEntry, GoldenPlaylist
from .errors import CatalogError


_REISSUE_MARKERS = ("reissue", "remaster", "deluxe")


@dataclass(frozen=True, slots=True)
class EditionOption:
    """One available edition on a platform (`ref` is the platform handle)."""
    ref: str
    title: str
    year: int | None = None


def choose_edition(
    options: list[EditionOption],
    preference: EditionPreference,
) -> tuple[EditionOption | None, str | None]:
    """Pick the best available edition given a preference; return (chosen, compromise).

    Selection order:
    1. First marker (in order) whose casefold text appears in any option title — no compromise.
    2. Most "original" option when prefer_original is set: lowest year (None sorts last),
       ties broken by absence of reissue/remaster/deluxe in title.
    3. Empty options → (None, None).
    """
    if not options:
        return None, None

    # Marker match: iterate markers in order; for each, find first matching option.
    for marker in preference.markers:
        for opt in options:
            if marker in opt.title.casefold():
                return opt, None

    # Fallback: prefer_original
    if preference.prefer_original:
        def _sort_key(opt: EditionOption):
            year_key = (1, opt.year) if opt.year is not None else (2, 0)
            reissue_key = 1 if any(m in opt.title.casefold() for m in _REISSUE_MARKERS) else 0
            return (year_key[0], year_key[1], reissue_key)

        chosen = min(options, key=_sort_key)
        compromise = (
            f"preferred edition ({preference.markers[0]}) unavailable"
            if preference.markers
            else None
        )
        return chosen, compromise

    # No preference applicable — return first option, no compromise.
    return options[0], None


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
