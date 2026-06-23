"""The realize stage: map a golden playlist onto one platform, best-effort.

A `Realizer` resolves a recording to a platform item (ISRC-first, then closeness) and
emits a playlist. `realize` resolves every admitted golden entry into a `Realization`
(resolved items + gaps) without writing; `publish` then emits the resolved items. The
two are separate so gaps can be reviewed before anything is created on the platform.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from .album import Album
from .edition import EditionPreference, EditionPolicy
from .identifiers import ISRC
from .recording import Recording
from .golden import GoldenEntry, GoldenPlaylist
from .errors import PlatformError
from .fidelity import (
    W_MARKER, W_TRACKLIST, W_TITLE, W_YEAR, W_REISSUE,
    EditionOption, edition_distance, choose_edition,
)


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
    items: tuple[PlatformItem, ...] = ()
    compromise: str | None = None

    @property
    def is_gap(self) -> bool:
        return not self.items


@dataclass(frozen=True, slots=True)
class Realization:
    name: str
    entries: tuple[RealizedEntry, ...]

    def resolved(self) -> tuple[RealizedEntry, ...]:
        return tuple(e for e in self.entries if not e.is_gap)

    def gaps(self) -> tuple[GoldenEntry, ...]:
        return tuple(e.golden for e in self.entries if e.is_gap)

    def compromises(self) -> tuple[tuple[GoldenEntry, str], ...]:
        return tuple(
            (e.golden, e.compromise)
            for e in self.entries
            if e.compromise is not None
        )


@runtime_checkable
class Realizer(Protocol):
    def resolve(self, recording: Recording) -> PlatformItem | None: ...
    def resolve_album(self, album: Album,
                      preference: EditionPreference) -> tuple[list[PlatformItem], str | None]: ...
    def emit(self, name: str, items: list[PlatformItem]) -> str: ...


def realize(
    golden: GoldenPlaylist,
    realizer: Realizer,
    preference: EditionPreference = EditionPolicy.default(),
) -> Realization:
    """Resolve every admitted golden entry to platform items (or a gap). No writes."""
    realized = []
    for e in golden.entries:
        if not e.verdict.admitted:
            continue
        if isinstance(e.item, Recording):
            pi = realizer.resolve(e.item)
            items = (pi,) if pi is not None else ()
            realized.append(RealizedEntry(e, items=items, compromise=None))
        elif isinstance(e.item, Album):
            effective_preference = e.edition if e.edition is not None else preference
            items_list, compromise = realizer.resolve_album(e.item, effective_preference)
            realized.append(RealizedEntry(e, items=tuple(items_list), compromise=compromise))
        else:
            realized.append(RealizedEntry(e, items=(), compromise=None))
    return Realization(golden.name, tuple(realized))


def publish(realization: Realization, realizer: Realizer) -> str:
    """Emit the resolved items to the platform; return the platform playlist reference."""
    items = [item for e in realization.resolved() for item in e.items]
    if not items:
        raise PlatformError(f"nothing resolved to publish for '{realization.name}'")
    return realizer.emit(realization.name, items)
