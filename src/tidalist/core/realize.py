"""The realize stage: map a golden playlist onto one platform, best-effort.

A `Realizer` resolves a recording to a platform item (ISRC-first, then closeness) and
emits a playlist. `realize` resolves every admitted golden entry into a `Realization`
(resolved items + gaps) without writing; `publish` then emits the resolved items. The
two are separate so gaps can be reviewed before anything is created on the platform.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from .album import Album, TrackRef
from .catalog import Track
from .edition import EditionPreference, EditionPolicy
from .identifiers import ISRC
from .recording import Recording
from .golden import GoldenEntry, GoldenPlaylist
from .errors import CatalogError


# ---------------------------------------------------------------------------
# Edition-distance metric
# ---------------------------------------------------------------------------

# Weight constants for the multi-dimensional edition distance.
# Dominance invariant: W_MARKER must strictly exceed the maximum possible sum of
# all other dimensions so a single-rank difference in marker always outranks any
# combination of content differences.
W_MARKER    = 1_000_000   # requested-marker rank (dominating dimension)
W_TRACKLIST = 100         # per-track count/missing penalty
W_TITLE     = 10          # title mismatch penalty
W_YEAR      = 1           # per-year distance from golden's first_released
W_REISSUE   = 5           # per kind-marker found in option title

# Markers that indicate non-original kind (reissues, expansions, live, etc.)
_KIND_MARKERS = (
    "reissue", "remaster", "deluxe", "live", "compilation", "expanded", "anniversary"
)


def _norm(s: str | None) -> str:
    """Normalise a string for comparison: casefold + strip."""
    return (s or "").casefold().strip()


@dataclass(frozen=True, slots=True)
class EditionOption:
    """One available edition on a platform (`ref` is the platform handle)."""
    ref: str
    title: str
    year: int | None = None
    tracks: tuple[Track, ...] = ()


def _track_matches(ref: TrackRef, t: Track) -> bool:
    """True if the golden TrackRef matches a platform Track by ISRC or normalised title."""
    if ref.isrc is not None and t.isrc is not None:
        return ref.isrc == t.isrc
    return _norm(ref.title) == _norm(t.title)


def edition_distance(
    golden: Album | None,
    option: EditionOption,
    preference: EditionPreference,
) -> float:
    """Compute a weighted distance between a golden Album and an EditionOption.

    Lower is better. Dimensions:
    - requested-marker (dominating): rank of the first preference marker found in option title
    - tracklist: count_diff + missing tracks (when golden has a tracklist)
    - title: mismatch between golden and option title (gated by prefer_original)
    - year: |option.year - golden.first_released| (gated by prefer_original)
    - reissue/kind: number of kind markers in option title (gated by prefer_original)
    """
    total = 0.0

    # --- Requested-marker dimension (always applies) ---
    title_lower = option.title.casefold()
    rank = min(
        (i for i, m in enumerate(preference.markers) if m in title_lower),
        default=len(preference.markers),
    )
    total += W_MARKER * rank

    # --- Tracklist dimension (always applies when golden has a tracklist) ---
    if golden is not None and golden.tracklist:
        count_diff = abs(len(golden.tracklist) - len(option.tracks))
        missing = sum(
            1 for g in golden.tracklist
            if not any(_track_matches(g, t) for t in option.tracks)
        )
        total += W_TRACKLIST * (count_diff + missing)

    # --- prefer_original-gated dimensions ---
    if preference.prefer_original:
        # Title dimension (requires golden)
        if golden is not None and _norm(golden.title) != _norm(option.title):
            total += W_TITLE

        # Year dimension (requires golden with first_released)
        if golden is not None and golden.first_released is not None:
            if option.year is not None:
                total += W_YEAR * abs(option.year - golden.first_released)
            else:
                # Unknown year is penalised as if arbitrarily far; use W_TITLE as a
                # reasonable upper bound (less than W_MARKER but more than a close year).
                total += W_TITLE

        # Reissue/kind dimension (applies whenever prefer_original is set)
        total += W_REISSUE * sum(1 for m in _KIND_MARKERS if m in title_lower)

    return total


def choose_edition(
    options: list[EditionOption],
    preference: EditionPreference,
    golden: Album | None = None,
) -> tuple[EditionOption | None, str | None]:
    """Pick the best available edition given a preference; return (chosen, compromise).

    Chooses the EditionOption with the minimum edition_distance from golden.
    A compromise is reported when markers were requested but none are present in
    the chosen option.
    """
    if not options:
        return None, None

    chosen = min(options, key=lambda o: edition_distance(golden, o, preference))

    # Determine compromise: markers were requested but the chosen edition carries none.
    compromise: str | None = None
    if preference.markers:
        chosen_title_lower = chosen.title.casefold()
        no_marker_matched = not any(m in chosen_title_lower for m in preference.markers)
        if no_marker_matched:
            compromise = f"preferred edition ({preference.markers[0]}) unavailable"

    return chosen, compromise


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
        raise CatalogError(f"nothing resolved to publish for '{realization.name}'")
    return realizer.emit(realization.name, items)
