"""Fidelity facets: per-dimension distance + compromise between a golden item and a
platform candidate. realize_distance sums the applicable facets; choose is the argmin.
Edition is the first facet ported here; identity/release-class/performance/quality follow.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .album import Album, ReleaseTrait, TrackRef
from .catalog import Track
from .edition import EditionPreference
from .identifiers import ISRC
from .recording import Performance, Recording

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

# Weight constant for identity facet (ISRC exactness).
# Must strictly exceed W_MARKER so a single ISRC mismatch dominates all other facets.
W_IDENTITY = 1_000_000_000  # identity dominates every other facet

# Markers that indicate non-original kind (reissues, expansions, live, etc.)
_KIND_MARKERS = (
    "reissue", "remaster", "deluxe", "live", "compilation", "expanded", "anniversary"
)


def _norm(s: str | None) -> str:
    """Normalise a string for comparison: casefold + strip."""
    return (s or "").casefold().strip()


@dataclass(frozen=True, slots=True)
class Compromise:
    """A reported deviation along one fidelity facet between desired and used."""
    facet: str
    desired: str
    used: str
    note: str


@dataclass(frozen=True, slots=True)
class EditionOption:
    """One available edition on a platform (`ref` is the platform handle)."""
    ref: str
    title: str
    year: int | None = None
    tracks: tuple[Track, ...] = ()


@dataclass(frozen=True, slots=True)
class PlatformCandidate:
    """A platform item carrying best-effort observed fidelity values. Unknowns stay
    None / UNKNOWN so the corresponding facet no-ops. `title`/`year`/`tracks` mirror
    EditionOption so edition_distance reads a candidate structurally."""
    ref: str
    title: str
    artists: tuple[str, ...] = ()
    isrc: ISRC | None = None
    year: int | None = None
    duration_s: int | None = None
    tracks: tuple[Track, ...] = ()
    release_class: frozenset[ReleaseTrait] | None = None
    performance: Performance = Performance.UNKNOWN
    source_kind: str | None = None
    audio_quality: str | None = None
    popularity: int | None = None


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


@dataclass(frozen=True, slots=True)
class EditionFacet:
    """Edition-fidelity facet: wraps edition_distance; no-ops only for Recordings."""
    preference: EditionPreference
    name: str = "edition"
    weight: float = 1.0

    def distance(self, golden, cand) -> float:
        # No-op only for recordings. golden may be None (legacy choose_edition):
        # edition_distance handles None and still scores marker + reissue dimensions.
        if isinstance(golden, Recording):
            return 0.0
        return edition_distance(golden, cand, self.preference)

    def compromise(self, golden, cand):
        if isinstance(golden, Recording) or not self.preference.markers:
            return None
        title_lower = cand.title.casefold()
        if any(m in title_lower for m in self.preference.markers):
            return None
        marker = self.preference.markers[0]
        return Compromise("edition", marker, "(no preferred edition)",
                          f"preferred edition ({marker}) unavailable")


@dataclass(frozen=True, slots=True)
class IdentityFacet:
    """ISRC exactness facet: penalizes recordings with mismatched ISRCs; albums always score 0."""
    name: str = "identity"
    weight: float = 1.0

    def distance(self, golden, cand) -> float:
        """Return W_IDENTITY if golden is a Recording with ISRC and both ISRCs are present but unequal;
        otherwise return 0.0 (golden is Album, or either ISRC is missing, or ISRCs match)."""
        if isinstance(golden, Recording) and golden.isrc is not None and cand.isrc is not None:
            return 0.0 if golden.isrc == cand.isrc else W_IDENTITY
        return 0.0

    def compromise(self, golden, cand):
        """Never emits a compromise."""
        return None


@runtime_checkable
class Facet(Protocol):
    name: str
    weight: float
    def distance(self, golden: "Album | Recording", cand: "PlatformCandidate") -> float: ...
    def compromise(self, golden: "Album | Recording",
                   cand: "PlatformCandidate") -> "Compromise | None": ...


def realize_distance(golden, cand, facets) -> float:
    return sum(f.weight * f.distance(golden, cand) for f in facets)


def choose(golden, candidates, facets):
    """Pick the candidate of minimum realize_distance (ties broken by ref for
    determinism); return it plus every facet's compromise on the winner."""
    if not candidates:
        return None, ()
    chosen = min(candidates, key=lambda c: (realize_distance(golden, c, facets), c.ref))
    comps = tuple(
        c for c in (f.compromise(golden, chosen) for f in facets) if c is not None
    )
    return chosen, comps


def choose_edition(
    options: list[EditionOption],
    preference: EditionPreference,
    golden: Album | None = None,
) -> tuple[EditionOption | None, str | None]:
    """Back-compat edition selector: delegates to choose over a single EditionFacet,
    returning the chosen option and a string compromise (or None)."""
    chosen, comps = choose(golden, options, [EditionFacet(preference)])
    return chosen, (comps[0].note if comps else None)
