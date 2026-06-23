# Uniform best-effort realize across all fidelity facets — design

> Status: design approved 2026-06-23 (brainstorm). Supersedes the single-axis
> `edition_distance` framing for the realize stage. Implementation is sliced (see
> below); each slice is its own PR/commit-set. Next step after this spec: an
> implementation plan via `superpowers:writing-plans`.

## Problem

Today the realize stage scores fidelity on **one** axis — *edition* —
(`core/realize.py::edition_distance` + `choose_edition`). The other fidelity
dimensions (identity, release-class, performance) are resolved at **curation** and
then, at realize time, either **gapped** or **silently substituted**. Both are wrong:

- **Silent substitution.** `TidalRealizer.resolve` (recording) does ISRC-first then a
  closeness search and returns the nearest hit with **no observation and no report** —
  if the studio ISRC is absent it can return a live take and say nothing.
- **Premature gap.** `resolve_album` gaps an album whose release-group is absent on the
  platform, even when the album's tracks exist on a compilation or live release.

The redesign makes realize a **uniform best-effort distance across all fidelity
dimensions**, with an honest per-dimension compromise report. `edition_distance` is the
first slice of a general `realize_distance(golden_item, platform_candidate)`.

## Decisions (locked in brainstorm 2026-06-23)

1. **Scope: full model, sliced build.** Spec the whole fidelity model so the
   abstraction is right; sequence implementation in additive slices (below).
2. **Always compromise; gap only on true identity absence.** The golden is the curated
   truth; realize renders it best-effort and is honest about deviations. Realize always
   substitutes the nearest candidate and reports a per-dimension compromise. A **gap**
   occurs only when *no* candidate clears identity at all. Brief criteria gate
   **curation** (golden membership) only — they never force a realize-time gap. This
   generalizes today's edition behavior (always pick nearest, report a compromise) to
   every dimension.
3. **Typed per-dimension compromises.** A realized entry carries a list of
   `Compromise(facet, desired, used, note)` — one per dimension it could not satisfy —
   replacing the single `RealizedEntry.compromise: str | None`.
4. **First-class `Facet` objects.** Each fidelity dimension is a small domain object
   (not a term inside one function, not a second parallel code path). `realize_distance`
   sums over the applicable facets; `choose` is a single argmin that then collects each
   facet's compromise on the winner.

### Naming (DDD)

The per-dimension type is **`Facet`** — a distinct face of a rendering's fidelity to the
golden. (Rejected: `Axis` — geometric, not domain language, the term this redesign
renames; `Criterion` — taken by the hard curation Specifications, and a facet is their
*graded/soft* sibling; `Trait` — taken by `ReleaseTrait`, and denotes a value not a
comparison; `Dimension` — as generic as `Axis`.)

## The model

### The observe / score split

Observation is platform-specific; distance and compromise are platform-agnostic. The
seam keeps `core/` pure and lets a richer backend improve observation with **no change
to facet logic**:

- **Adapter observes** → a new core value object **`PlatformCandidate`** carries the
  best-effort *observed* values: `ref, title, artists, isrc` + `release_class:
  frozenset[ReleaseTrait] | None`, `performance: Performance`, edition fields (`year`,
  `tracks: tuple[Track, ...]`), and quality signals (`source_kind`, `audio_quality`,
  `popularity` — all optional). `TidalPlatform` / `TidalRealizer` populate what Tidal
  exposes: ISRC identity now, plus title-marker heuristics for release-class /
  performance / edition. A torrent/local backend later fills the structured fields with
  no core change. Unknown stays `None` / `UNKNOWN` and the relevant facet no-ops.
- **Core scores** → first-class `Facet` objects.

```python
# core, pure
class Facet(Protocol):
    name: str
    weight: float
    def distance(self, golden: Album | Recording, cand: PlatformCandidate) -> float: ...
    def compromise(self, golden: Album | Recording,
                   cand: PlatformCandidate) -> Compromise | None: ...
```

Concrete facets: `IdentityFacet`, `ReleaseClassFacet`, `PerformanceFacet`,
`EditionFacet` (today's `edition_distance` moves here), `AudioFacet`. Each **no-ops to
distance 0 / no compromise when not applicable** to the golden item's type — the same
type-aware rule the criteria already use (recording facets no-op on albums and
vice-versa).

```python
def realize_distance(golden, cand, facets) -> float:
    return sum(f.weight * f.distance(golden, cand) for f in facets)

def choose(golden, cands, facets) -> tuple[PlatformCandidate | None, tuple[Compromise, ...]]:
    # argmin realize_distance, then collect each facet's compromise on the winner
```

### Typed compromise

```python
@dataclass(frozen=True, slots=True)
class Compromise:
    facet: str     # "performance", "edition", "release-class", "album-source", ...
    desired: str   # e.g. "studio"
    used: str      # e.g. "live"
    note: str      # rendered explanation
```

`RealizedEntry.compromise: str | None` → `compromises: tuple[Compromise, ...]`.
`Realization.compromises()` flattens to `tuple[tuple[GoldenEntry, Compromise], ...]`.
`Realization` is **ephemeral** (printed by the `realize`/`review` verbs, not persisted)
— so there is **no golden-JSON schema change**.

### Weight ladder & dominance

Lexicographic via weighted constants (generalizing today's `edition_distance` weights):

```
identity ≫ requested-marker ≫ release-class / performance ≫ edition-content (tracklist/title/year) ≫ quality
```

where *requested-marker* is `EditionFacet`'s explicitly-requested edition marker
(Steven Wilson / Mobile Fidelity) — today's dominating `W_MARKER` dimension. (In
practice identity dominates both marker and performance, since editions of one release
share a performance, so marker-vs-performance rarely conflict; the ordering is tunable.)

`AudioFacet` (quality) is the **lowest** weight, so it decides only when everything above
ties — a pure distance-0 tiebreak that removes the current `min()` arbitrary-list-order
non-determinism. The constants are tunable; the dominance invariant (a higher facet's
unit difference outranks any sum below it) is documented at the constants, same posture
as today's `W_MARKER` note.

## Resolution flow

Both recording and album realize funnel through `choose`:

- **Recording.** Adapter builds candidates from ISRC lookup + search hits → `choose` →
  one `PlatformItem`. Applicable facets: `Identity`, `Performance`, `Audio`.
- **Album.** Adapter builds candidates from anchor search → discography editions (each
  edition a candidate with observed `tracks`) → `choose` → expand the chosen edition to
  its track `PlatformItem`s. Applicable facets: `Identity`, `ReleaseClass`, `Edition`,
  `Audio`.

### No-silent-substitution

`PerformanceFacet` observes the candidate's performance (distinct-ISRC identity + title
markers like "live at"). If the chosen recording's performance ≠ the golden's desired,
it emits `Compromise(performance, desired="studio", used="live", …)`. Always substitute
the nearest; always report.

### Gap = true identity absence

A gap occurs only when **no** candidate clears `IdentityFacet`'s "present" threshold.
A mere class/performance/edition mismatch is never a gap — it is the nearest candidate
plus a compromise.

### Track-level album fallback

When the whole-edition path finds no edition that clears identity (release-group absent
on the platform), **do not gap** — assemble the canonical tracklist track-by-track: for
each `TrackRef` in `golden.tracklist`, run the *recording* path (the same `choose`) to
find that track anywhere on the platform (a compilation, a live album, a different
release). Emit one `Compromise(album-source, used="assembled from N releases", …)`.
Positions still unfound are reported as a **partial** (the entry lists the missing
positions). Only **zero** tracks found → gap.

## Implementation slices

Each slice is its own PR/commit-set; slice 1 lands the reshape (value objects + CLI) so
later slices are additive.

### Slice 1 — Abstraction + edition migration (behavior-preserving)
- New core: `Facet`, `PlatformCandidate`, `Compromise`, `realize_distance`, `choose`.
- Migrate `edition_distance` → `EditionFacet.distance`; add `IdentityFacet`
  (tracklist-overlap for albums, ISRC for recordings).
- Reshape `RealizedEntry.compromise` → `compromises: tuple[Compromise, ...]`; update
  `Realization.compromises()` and the CLI formatter (`format_realization`).
- `AudioFacet` lands as a **deterministic tiebreak only** (stable; kills the `min()`
  non-determinism). Rich policy deferred to slice 4.
- Album realize reimplemented on `choose`. **Acceptance:** the Mr. Fantasy 10-track
  live proof and all 293 offline tests stay green.

### Slice 2 — Recording facets + no-silent-substitution
- `PerformanceFacet` (+ recording observation: ISRC identity + title markers).
- `ReleaseClassFacet` (album comp/live observation from title/identity).
- Recording realize funnels through `choose`; emits the performance compromise.
- **Acceptance:** studio asked, only a live take available → substitutes + reports the
  performance compromise (unit + a live integration case).

### Slice 3 — Track-level album fallback (most ambitious; live-fixture gated)
- Per-track assembly when no edition clears identity; `Compromise(album-source)` +
  missing-positions partial.
- **Live fixture: Captain Beefheart — _Trout Mask Replica_.** The album itself is absent
  on Tidal, but many of its tracks are present via compilations — the realistic
  **partial** case: the entry assembles from compilation sources and reports the
  positions Tidal still lacks. (`tests/realize/test_track_fallback_live.py`,
  `@pytest.mark.integration`.)
- **Acceptance:** _Trout Mask Replica_ → assembled from comp sources + `album-source`
  compromise + reported missing positions (partial, not a gap); a synthetic
  zero-tracks-found case → gap.

### Slice 4 — Quality-preference policy depth
- Flesh `AudioFacet` into a **specifiable** policy (original-source > comp, hi-res >
  lossy, popularity), `EditionPreference`-shaped, with a documented default ordering.
- **Acceptance:** tie cases broken deterministically by the policy (same ISRC on the
  original vs a comp → original; hi-res vs lossy → hi-res).

## Testing strategy

- Pure-domain unit tests carry the bulk — `Facet` distance/compromise, `choose`,
  `realize_distance`, facet no-op-by-type — ms, no I/O.
- Adapter observation tested against fakes anchored to **probed real tidalapi
  signatures**; then `@pytest.mark.integration` live cases for the new shapes
  (performance substitution; track-level assembly — Captain Beefheart's _Trout Mask
  Replica_, absent as an album but partly present via compilations).
- All 293 offline tests stay green throughout; slice 1 is behavior-preserving.

## Tunable / open (carried forward, not blocking)

- Cross-facet weight constants and the dominance invariant are first-cut (generalize
  today's `edition_distance` constants). Revisit if a real playlist misselects.
- `AudioFacet` observation depth on Tidal is limited to its audio-quality flag +
  popularity; the structured `source_kind` dimension is only meaningful once a
  rich-metadata backend (torrent/local) lands.
- `IdentityFacet`'s "present" threshold (the gap boundary) is a domain-bounded constant;
  validate against a corpus.
