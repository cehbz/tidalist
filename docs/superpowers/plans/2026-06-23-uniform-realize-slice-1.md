# Uniform Realize — Slice 1 (Abstraction + Edition Migration) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce the uniform fidelity-facet abstraction (`Facet`, `PlatformCandidate`, `Compromise`, `realize_distance`, `choose`) in a new `core/fidelity.py`, migrate the existing edition selection onto it, and reshape the realize stage's compromise reporting from a single `str` to typed per-facet `Compromise` objects — all **behavior-preserving** (the Mr. Fantasy 10-track edition still wins; all 293 offline tests stay green).

**Architecture:** Ports-and-adapters around a pure DDD core (see the project README + KB). The realize stage scores how faithfully a platform candidate matches a golden item along independent **facets**. Each facet is a first-class core object computing a per-dimension `distance` and `compromise`; `realize_distance` sums the applicable facets and `choose` is the argmin. Observation of facet values is the adapter's job (packed into `PlatformCandidate`); scoring is the pure core's. Slice 1 builds the framework and ports only the **edition** and **identity** facets; release-class, performance, track-level fallback, and the quality preference come in slices 2–4.

**Tech Stack:** Python 3.12 (uv), stdlib-only domain core; `pytest`. Run via `uv run`.

## Global Constraints

- uv only; run tests via `uv run pytest -m "not integration"` (fast offline suite) and `uv run pytest` (includes live `@pytest.mark.integration`, needs creds). `pythonpath=["src","."]`.
- Domain (`core/`) is **pure**: no I/O, no third-party imports. Value objects are `@dataclass(frozen=True, slots=True)`.
- Outbound deps are `typing.Protocol` ports (consumer-defined, structural). Core imports no adapter.
- DDD ubiquitous language; behavior on the owning object. Terse docstrings: state what exists.
- TDD red→green→refactor; watch each test fail first (a *failing assertion*, not an import error). Fakes over mocks.
- Structured errors; no bare `except`; no silent swallow in core. Presentation stays in the CLI layer.
- **Behavior-preserving slice:** no live-observable selection change. The Mr. Fantasy live proof (`tests/realize/test_edition_distance_live.py`) and all 293 offline tests stay green.
- Per the project commit checkpoint: each task's commit message must be approved by the user before committing (this plan shows the message; the executor still stops for approval).

## Design notes (decisions locked in the spec `docs/superpowers/specs/2026-06-23-uniform-realize-design.md`)

- **Always compromise; gap only on true identity absence.** Realize substitutes the nearest candidate and reports a per-facet compromise; a gap means identity matched nothing. Slice 1 keeps today's album gap behavior (empty survivors → gap) and adds typed compromises.
- **`Facet`** is the per-fidelity-dimension type (named in the spec; rejected `Axis`/`Criterion`/`Trait`/`Dimension`).
- **Observe in adapter, score in core.** The adapter packs observed values into `PlatformCandidate`; facets read them.
- **Two minor implementation refinements vs. the spec wording, both within latitude:**
  1. The slice-1 **deterministic tiebreak** is implemented as `choose`'s secondary sort key (`candidate.ref`), *not* a stub `AudioFacet`. `AudioFacet` is wholly slice 4. This still removes the current `min()` arbitrary-list-order non-determinism.
  2. The cross-facet **weight ladder** is carried by each facet's internal constants (`W_IDENTITY` in `IdentityFacet`; the existing `W_MARKER`/`W_TRACKLIST`/… inside `edition_distance`), with every `Facet.weight == 1.0` in slice 1. Dominance invariant: `W_IDENTITY ≫ W_MARKER ≫ W_TRACKLIST ≫ W_TITLE/W_REISSUE ≫ W_YEAR`.

## File structure

- **Create `src/tidalist/core/fidelity.py`** — the fidelity framework: moved edition-distance math (`edition_distance`, `EditionOption`, `choose_edition`, weight constants, `_KIND_MARKERS`, `_norm`, `_track_matches`) + new `Compromise`, `PlatformCandidate`, `Facet`, `realize_distance`, `choose`, `IdentityFacet`, `EditionFacet`, `W_IDENTITY`.
- **Modify `src/tidalist/core/realize.py`** — drop the moved edition math; re-export it from `fidelity` for back-compat; keep `MatchQuality`, `PlatformItem`, `RealizedEntry` (reshaped), `Realization` (reshaped), `Realizer` (contract updated), `realize()`, `publish()`.
- **Modify `src/tidalist/realize/tidal.py`** — `resolve_album` rebuilt on `choose`; imports updated.
- **Modify `src/tidalist/cli.py`** — `format_realization` renders typed compromises.
- **Modify `tests/fakes.py`** and **`tests/core/test_realize.py`'s `_FakeRealizer`** — `resolve_album` returns `tuple[Compromise, ...]`.
- **Modify tests** — `tests/core/test_realize.py`, `tests/realize/test_tidal.py`, `tests/test_cli.py` migrate compromise assertions.
- **Create `tests/core/test_fidelity.py`** — unit tests for the new framework.

---

## Task 1: Scaffold `core/fidelity.py` (move + re-export, behavior-preserving)

**Files:**
- Create: `src/tidalist/core/fidelity.py`
- Modify: `src/tidalist/core/realize.py`

**Interfaces:**
- Produces: module `tidalist.core.fidelity` exporting `W_MARKER, W_TRACKLIST, W_TITLE, W_YEAR, W_REISSUE, _KIND_MARKERS, _norm, EditionOption, _track_matches, edition_distance, choose_edition`. `tidalist.core.realize` re-exports all of these unchanged (existing imports `from tidalist.core.realize import EditionOption, choose_edition, edition_distance` keep working).

- [ ] **Step 1: Create `fidelity.py` with the moved edition math.** Move verbatim from `realize.py` (current lines 22–141): the weight constants block, `_KIND_MARKERS`, `_norm`, `EditionOption`, `_track_matches`, `edition_distance`, `choose_edition`. The new file header and imports:

```python
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

# (moved verbatim from realize.py: W_MARKER … choose_edition)
```

- [ ] **Step 2: Strip the moved symbols from `realize.py` and re-export.** Remove the moved block (old lines 22–141) from `realize.py`. Replace the edition imports at the top of `realize.py` with a re-export from `fidelity`:

```python
from .fidelity import (
    W_MARKER, W_TRACKLIST, W_TITLE, W_YEAR, W_REISSUE,
    EditionOption, edition_distance, choose_edition,
)
```

Keep only the imports `realize.py` still uses after the move (`Album`, `EditionPreference`, `EditionPolicy`, `ISRC`, `Recording`, `GoldenEntry`, `GoldenPlaylist`, `PlatformError`); **drop `TrackRef` and `Track`**, which were only used by the moved edition math and are now dead in `realize.py`.

- [ ] **Step 3: Run the full offline suite to verify the move is behavior-preserving.**

Run: `uv run pytest -m "not integration" -q`
Expected: PASS (same count as before, 293). A pure move + re-export changes no behavior.

- [ ] **Step 4: Commit.**

```bash
git add src/tidalist/core/fidelity.py src/tidalist/core/realize.py
git commit -m "refactor(core): extract the edition-distance math into core/fidelity.py"
```

---

## Task 2: `Compromise` value object

**Files:**
- Modify: `src/tidalist/core/fidelity.py`
- Test: `tests/core/test_fidelity.py`

**Interfaces:**
- Produces: `Compromise(facet: str, desired: str, used: str, note: str)` — frozen/slots value object.

- [ ] **Step 1: Write the failing test.**

```python
# tests/core/test_fidelity.py
from tidalist.core.fidelity import Compromise


def test_compromise_carries_facet_desired_used_note():
    c = Compromise(facet="edition", desired="steven wilson",
                   used="(no preferred edition)", note="preferred edition unavailable")
    assert c.facet == "edition"
    assert c.desired == "steven wilson"
    assert c.used == "(no preferred edition)"
    assert "unavailable" in c.note
```

- [ ] **Step 2: Run it to verify it fails.**

Run: `uv run pytest tests/core/test_fidelity.py::test_compromise_carries_facet_desired_used_note -v`
Expected: FAIL — `ImportError: cannot import name 'Compromise'` is an import error, which does not count as red; so first add a stub `class Compromise: ...` that omits the fields, run again, and confirm the assertion fails (`TypeError`/`AttributeError`). Then implement.

- [ ] **Step 3: Implement.**

```python
@dataclass(frozen=True, slots=True)
class Compromise:
    """A reported deviation along one fidelity facet between desired and used."""
    facet: str
    desired: str
    used: str
    note: str
```

- [ ] **Step 4: Run to verify it passes.**

Run: `uv run pytest tests/core/test_fidelity.py -v`
Expected: PASS

- [ ] **Step 5: Commit.**

```bash
git add src/tidalist/core/fidelity.py tests/core/test_fidelity.py
git commit -m "feat(core): Compromise — a typed per-facet realize deviation"
```

---

## Task 3: `PlatformCandidate` value object

**Files:**
- Modify: `src/tidalist/core/fidelity.py`
- Test: `tests/core/test_fidelity.py`

**Interfaces:**
- Produces: `PlatformCandidate(ref, title, artists=(), isrc=None, year=None, tracks=(), release_class=None, performance=Performance.UNKNOWN, source_kind=None, audio_quality=None, popularity=None)`. Note `title`/`year`/`tracks` are deliberately named to match `EditionOption` so `edition_distance` reads a `PlatformCandidate` structurally.

- [ ] **Step 1: Write the failing test.**

```python
def test_platform_candidate_defaults_are_observation_unknowns():
    from tidalist.core.fidelity import PlatformCandidate
    from tidalist.core.recording import Performance
    c = PlatformCandidate(ref="A1", title="Mr. Fantasy")
    assert c.artists == () and c.isrc is None and c.year is None and c.tracks == ()
    assert c.release_class is None
    assert c.performance is Performance.UNKNOWN
    assert c.source_kind is None and c.audio_quality is None and c.popularity is None
```

- [ ] **Step 2: Run to verify it fails.** (Add an empty `class PlatformCandidate: ...` stub first if needed so it's an assertion failure, not an import error.)

Run: `uv run pytest tests/core/test_fidelity.py::test_platform_candidate_defaults_are_observation_unknowns -v`
Expected: FAIL on the attribute assertions.

- [ ] **Step 3: Implement.**

```python
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
    tracks: tuple[Track, ...] = ()
    release_class: frozenset[ReleaseTrait] | None = None
    performance: Performance = Performance.UNKNOWN
    source_kind: str | None = None
    audio_quality: str | None = None
    popularity: int | None = None
```

- [ ] **Step 4: Run to verify it passes.**

Run: `uv run pytest tests/core/test_fidelity.py -v`
Expected: PASS

- [ ] **Step 5: Commit.**

```bash
git add src/tidalist/core/fidelity.py tests/core/test_fidelity.py
git commit -m "feat(core): PlatformCandidate — best-effort observed fidelity values"
```

---

## Task 4: `Facet` protocol + `realize_distance` + `choose`

**Files:**
- Modify: `src/tidalist/core/fidelity.py`
- Test: `tests/core/test_fidelity.py`

**Interfaces:**
- Consumes: `PlatformCandidate`, `Compromise`.
- Produces:
  - `Facet` (Protocol): attrs `name: str`, `weight: float`; methods `distance(golden, cand) -> float`, `compromise(golden, cand) -> Compromise | None`.
  - `realize_distance(golden, cand, facets) -> float` = `sum(f.weight * f.distance(golden, cand) for f in facets)`.
  - `choose(golden, candidates, facets) -> tuple[PlatformCandidate | None, tuple[Compromise, ...]]` = argmin of `(realize_distance, candidate.ref)`; on the winner, collect each facet's non-None `compromise`. Empty candidates → `(None, ())`.

- [ ] **Step 1: Write the failing tests** (use a tiny in-test fake facet; assert the secondary-key tiebreak is deterministic).

```python
from dataclasses import dataclass as _dc
from tidalist.core.fidelity import PlatformCandidate, Compromise, realize_distance, choose
from tidalist.core.recording import Recording


@_dc
class _FixedFacet:
    name = "fixed"
    weight = 1.0
    table: dict          # ref -> distance
    note: str | None = None
    def distance(self, golden, cand): return self.table[cand.ref]
    def compromise(self, golden, cand):
        return Compromise("fixed", "x", "y", self.note) if self.note else None


def test_realize_distance_sums_weighted_facets():
    cand = PlatformCandidate(ref="A", title="t")
    g = Recording(artist="a", title="t")
    facets = [_FixedFacet(table={"A": 2.0}), _FixedFacet(table={"A": 3.0})]
    assert realize_distance(g, cand, facets) == 5.0


def test_choose_returns_min_distance_candidate_and_its_compromises():
    g = Recording(artist="a", title="t")
    c_near = PlatformCandidate(ref="near", title="t")
    c_far = PlatformCandidate(ref="far", title="t")
    facets = [_FixedFacet(table={"near": 1.0, "far": 9.0}, note="used a substitute")]
    chosen, comps = choose(g, [c_far, c_near], facets)
    assert chosen.ref == "near"
    assert len(comps) == 1 and comps[0].note == "used a substitute"


def test_choose_breaks_ties_deterministically_by_ref():
    g = Recording(artist="a", title="t")
    a = PlatformCandidate(ref="a", title="t")
    b = PlatformCandidate(ref="b", title="t")
    facets = [_FixedFacet(table={"a": 5.0, "b": 5.0})]
    # Equal distance → lexicographically smaller ref wins, regardless of input order.
    assert choose(g, [b, a], facets)[0].ref == "a"
    assert choose(g, [a, b], facets)[0].ref == "a"


def test_choose_empty_candidates_returns_none_and_no_compromises():
    g = Recording(artist="a", title="t")
    assert choose(g, [], [_FixedFacet(table={})]) == (None, ())
```

- [ ] **Step 2: Run to verify they fail.**

Run: `uv run pytest tests/core/test_fidelity.py -k "realize_distance or choose_returns or choose_breaks or choose_empty" -v`
Expected: FAIL (`choose`/`realize_distance` not defined → add minimal stubs returning `0.0` / `(None, ())` so the suite runs, then confirm assertion failures).

- [ ] **Step 3: Implement.**

```python
@runtime_checkable
class Facet(Protocol):
    name: str
    weight: float
    def distance(self, golden: Album | Recording, cand: "PlatformCandidate") -> float: ...
    def compromise(self, golden: Album | Recording,
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
```

- [ ] **Step 4: Run to verify they pass.**

Run: `uv run pytest tests/core/test_fidelity.py -v`
Expected: PASS

- [ ] **Step 5: Commit.**

```bash
git add src/tidalist/core/fidelity.py tests/core/test_fidelity.py
git commit -m "feat(core): Facet protocol + realize_distance + choose (argmin, deterministic tiebreak)"
```

---

## Task 5: `IdentityFacet`

**Files:**
- Modify: `src/tidalist/core/fidelity.py`
- Test: `tests/core/test_fidelity.py`

**Interfaces:**
- Consumes: `Recording`, `Album`, `PlatformCandidate`, `W_IDENTITY`.
- Produces: `IdentityFacet(name="identity", weight=1.0)`. Recording: ISRC present on both and unequal → `W_IDENTITY`, else `0.0`. Album: `0.0` (adapter pre-filters survivors to the release identity; the album gap boundary is the survivor search, made explicit in slice 3). Never emits a compromise.
- Adds constant `W_IDENTITY = 1_000_000_000` (≫ `W_MARKER`).

- [ ] **Step 1: Write the failing tests.**

```python
from tidalist.core.fidelity import IdentityFacet, PlatformCandidate, W_IDENTITY, W_MARKER
from tidalist.core.identifiers import ISRC
from tidalist.core.recording import Recording
from tidalist.core.album import Album


def test_identity_dominates_marker():
    assert W_IDENTITY > W_MARKER


def test_identity_recording_isrc_match_is_zero():
    g = Recording(artist="Traffic", title="Glad", isrc=ISRC("GB1"))
    cand = PlatformCandidate(ref="t1", title="Glad", isrc=ISRC("GB1"))
    assert IdentityFacet().distance(g, cand) == 0.0


def test_identity_recording_isrc_mismatch_is_w_identity():
    g = Recording(artist="Traffic", title="Glad", isrc=ISRC("GB1"))
    cand = PlatformCandidate(ref="t2", title="Glad", isrc=ISRC("GB2"))
    assert IdentityFacet().distance(g, cand) == W_IDENTITY


def test_identity_recording_unknown_isrc_is_zero():
    g = Recording(artist="Traffic", title="Glad")          # no isrc
    cand = PlatformCandidate(ref="t3", title="Glad", isrc=ISRC("GB9"))
    assert IdentityFacet().distance(g, cand) == 0.0


def test_identity_album_is_zero():
    g = Album(artist="Traffic", title="Mr. Fantasy")
    cand = PlatformCandidate(ref="A1", title="Mr. Fantasy")
    assert IdentityFacet().distance(g, cand) == 0.0
    assert IdentityFacet().compromise(g, cand) is None
```

- [ ] **Step 2: Run to verify they fail.**

Run: `uv run pytest tests/core/test_fidelity.py -k identity -v`
Expected: FAIL (`IdentityFacet`/`W_IDENTITY` not defined — add a stub returning `0.0` to get past import, then see the mismatch assertion fail).

- [ ] **Step 3: Implement.**

```python
W_IDENTITY = 1_000_000_000   # identity dominates every other facet


@dataclass(frozen=True, slots=True)
class IdentityFacet:
    name: str = "identity"
    weight: float = 1.0

    def distance(self, golden, cand) -> float:
        if isinstance(golden, Recording) and golden.isrc is not None and cand.isrc is not None:
            return 0.0 if golden.isrc == cand.isrc else W_IDENTITY
        return 0.0

    def compromise(self, golden, cand):
        return None
```

- [ ] **Step 4: Run to verify they pass.**

Run: `uv run pytest tests/core/test_fidelity.py -k identity -v`
Expected: PASS

- [ ] **Step 5: Commit.**

```bash
git add src/tidalist/core/fidelity.py tests/core/test_fidelity.py
git commit -m "feat(core): IdentityFacet — ISRC exactness (dominant), album pre-filtered"
```

---

## Task 6: `EditionFacet` + rewrite `choose_edition` to delegate

**Files:**
- Modify: `src/tidalist/core/fidelity.py`
- Test: `tests/core/test_fidelity.py` (new), `tests/core/test_realize.py` (existing `choose_edition` tests must stay green)

**Interfaces:**
- Consumes: `EditionPreference`, `edition_distance`, `Compromise`, `Album`, `choose`.
- Produces: `EditionFacet(preference: EditionPreference, name="edition", weight=1.0)`.
  - `distance(golden, cand)`: `0.0` only when `golden` is a `Recording`; otherwise `edition_distance(golden, cand, self.preference)` (reads `cand.title/.year/.tracks` structurally). **`golden` may be `None`** (the legacy `choose_edition` path) — `edition_distance` handles `None`, still computing the marker + reissue dimensions, so the facet must delegate, not no-op, on `None`.
  - `compromise(golden, cand) -> Compromise | None`: `None` when `golden` is a `Recording`, or `preference.markers` is empty, or a marker is in `cand.title.casefold()`; else `Compromise("edition", preference.markers[0], "(no preferred edition)", f"preferred edition ({preference.markers[0]}) unavailable")`. (Independent of `golden`, matching the old `choose_edition` compromise logic.)
- `choose_edition(options, preference, golden=None)` is **rewritten** to delegate: `chosen, comps = choose(golden, options, [EditionFacet(preference)])`; `return chosen, (comps[0].note if comps else None)`. Its existing tests (return `(EditionOption | None, str | None)`) stay green.

- [ ] **Step 1: Write the failing facet tests** (`tests/core/test_fidelity.py`).

```python
from tidalist.core.fidelity import EditionFacet, PlatformCandidate, edition_distance
from tidalist.core.edition import EditionPreference
from tidalist.core.album import Album
from tidalist.core.recording import Recording


def test_edition_facet_distance_matches_edition_distance_for_albums():
    g = Album(artist="Yes", title="Close to the Edge", first_released=1972)
    pref = EditionPreference(markers=(), prefer_original=True)
    cand = PlatformCandidate(ref="orig", title="Close to the Edge", year=1972)
    assert EditionFacet(pref).distance(g, cand) == edition_distance(g, cand, pref)


def test_edition_facet_no_op_on_recordings():
    g = Recording(artist="Yes", title="Roundabout")
    pref = EditionPreference(markers=("steven wilson",))
    cand = PlatformCandidate(ref="x", title="Roundabout")
    assert EditionFacet(pref).distance(g, cand) == 0.0
    assert EditionFacet(pref).compromise(g, cand) is None


def test_edition_facet_compromise_when_no_marker_present():
    g = Album(artist="Yes", title="Close to the Edge", first_released=1972)
    pref = EditionPreference(markers=("steven wilson",), prefer_original=True)
    cand = PlatformCandidate(ref="orig", title="Close to the Edge", year=1972)
    comp = EditionFacet(pref).compromise(g, cand)
    assert comp is not None
    assert comp.facet == "edition" and comp.desired == "steven wilson"
    assert comp.note == "preferred edition (steven wilson) unavailable"


def test_edition_facet_no_compromise_when_marker_present():
    g = Album(artist="Yes", title="Close to the Edge", first_released=1972)
    pref = EditionPreference(markers=("steven wilson",))
    cand = PlatformCandidate(ref="sw", title="Close to the Edge (Steven Wilson Mix)", year=2013)
    assert EditionFacet(pref).compromise(g, cand) is None
```

- [ ] **Step 2: Run to verify they fail.**

Run: `uv run pytest tests/core/test_fidelity.py -k edition_facet -v`
Expected: FAIL (`EditionFacet` undefined → stub, then assertion failures).

- [ ] **Step 3: Implement `EditionFacet` and rewrite `choose_edition`.**

```python
@dataclass(frozen=True, slots=True)
class EditionFacet:
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
```

Rewrite `choose_edition` (replace its body) to delegate:

```python
def choose_edition(options, preference, golden=None):
    """Back-compat edition selector: delegates to choose over a single EditionFacet,
    returning the chosen option and a string compromise (or None)."""
    chosen, comps = choose(golden, options, [EditionFacet(preference)])
    return chosen, (comps[0].note if comps else None)
```

- [ ] **Step 4: Run the new facet tests AND the existing `choose_edition` tests.**

Run: `uv run pytest tests/core/test_fidelity.py tests/core/test_realize.py -k "edition_facet or choose_edition" -v`
Expected: PASS — the facet tests pass and all existing `choose_edition` tests stay green (delegation is behavior-equivalent; the `ref` tiebreak only changes selection among exactly-tied distances, of which these tests have none).

- [ ] **Step 5: Run the full offline suite** to confirm no regression in edition selection (`edition_distance` tests, `resolve_album` tests still use the old `resolve_album` path).

Run: `uv run pytest -m "not integration" -q`
Expected: PASS (293).

- [ ] **Step 6: Commit.**

```bash
git add src/tidalist/core/fidelity.py tests/core/test_fidelity.py
git commit -m "feat(core): EditionFacet; choose_edition delegates to choose"
```

---

## Task 7: Reshape compromises to typed; flip the `resolve_album` contract (core side)

**Files:**
- Modify: `src/tidalist/core/realize.py`, `src/tidalist/cli.py`, `tests/fakes.py`
- Test: `tests/core/test_realize.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `Compromise` (from `fidelity`).
- Produces (contract changes):
  - `RealizedEntry(golden, items=(), compromises: tuple[Compromise, ...] = ())` — the `compromise: str | None` field is **removed**; `is_gap` unchanged.
  - `Realization.compromises() -> tuple[tuple[GoldenEntry, Compromise], ...]` — flattens each entry's typed compromises.
  - `Realizer.resolve_album(album, preference) -> tuple[list[PlatformItem], tuple[Compromise, ...]]`.
  - `Realizer.resolve(recording) -> PlatformItem | None` (unchanged; recording compromises arrive in slice 2).
  - Both fakes' `resolve_album` default returns `[], ()`.

- [ ] **Step 1: Migrate the failing core tests first** (write them red against the new shape). In `tests/core/test_realize.py`:
  - Update `_FakeRealizer.resolve_album` default `return [], None` → `return [], ()`, and its docstring to say it returns `(items_list, tuple[Compromise, ...])`.
  - Rewrite `test_album_entry_compromise_surfaces_in_compromises` to use a typed compromise:

```python
def test_album_entry_compromise_surfaces_in_compromises():
    from tidalist.core.fidelity import Compromise
    track1 = PlatformItem(ref="t1", title="Glad", artists=("Traffic",))
    album = Album(artist="Traffic", title="John Barleycorn Must Die")
    entry = GoldenEntry(album, Provenance("nl"), Verdict.ok())
    g = _golden(entry)
    comp = Compromise("edition", "steven wilson", "(no preferred edition)",
                      "preferred edition (steven wilson) unavailable")
    realizer = _FakeRealizer({}, albums={"John Barleycorn Must Die": ([track1], (comp,))})
    r = realize(g, realizer)
    comps = r.compromises()
    assert len(comps) == 1
    golden_e, got = comps[0]
    assert golden_e.item.title == "John Barleycorn Must Die"
    assert got.facet == "edition" and "steven wilson" in got.note
```

  - Update `test_compromises_empty_when_no_compromise` album value `([track1], None)` → `([track1], ())`.
  - Update `_PreferenceCapturingRealizer` album values `([PlatformItem(...)], None)` → `([PlatformItem(...)], ())` (both `test_realize_uses_entry_edition_*` tests).

- [ ] **Step 2: Migrate the CLI test** (`tests/test_cli.py::test_format_realization_shows_compromise_note`):

```python
def test_format_realization_shows_compromise_note():
    from tidalist.core.album import Album
    from tidalist.core.golden import GoldenEntry
    from tidalist.core.provenance import Provenance
    from tidalist.core.criteria import Verdict
    from tidalist.core.fidelity import Compromise

    t1 = PlatformItem(ref="t1", title="Glad", artists=("Traffic",))
    album = Album(artist="Traffic", title="John Barleycorn Must Die")
    golden_entry = GoldenEntry(album, Provenance("nl"), Verdict.ok())
    comp = Compromise("edition", "steven wilson", "(none)", "preferred edition unavailable")
    r = Realization("Traffic Albums", (
        RealizedEntry(golden_entry, items=(t1,), compromises=(comp,)),
    ))
    text = cli.format_realization(r)
    assert "compromise" in text
    assert "preferred edition unavailable" in text
```

- [ ] **Step 3: Run the migrated tests to verify they fail.**

Run: `uv run pytest tests/core/test_realize.py tests/test_cli.py -k "compromise or entry_edition" -v`
Expected: FAIL — `RealizedEntry`/`Realization`/`format_realization` still use the old `str` field; `compromises=` keyword and typed `compromises()` not present yet.

- [ ] **Step 4: Reshape `RealizedEntry` / `Realization` in `realize.py`.** Import `Compromise`: change the `from .fidelity import (...)` block to also import `Compromise`. Then:

```python
@dataclass(frozen=True, slots=True)
class RealizedEntry:
    golden: GoldenEntry
    items: tuple[PlatformItem, ...] = ()
    compromises: tuple[Compromise, ...] = ()

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

    def compromises(self) -> tuple[tuple[GoldenEntry, Compromise], ...]:
        return tuple((e.golden, c) for e in self.entries for c in e.compromises)
```

Update the `Realizer` protocol and `realize()`:

```python
class Realizer(Protocol):
    def resolve(self, recording: Recording) -> PlatformItem | None: ...
    def resolve_album(self, album: Album,
                      preference: EditionPreference) -> tuple[list[PlatformItem], tuple[Compromise, ...]]: ...
    def emit(self, name: str, items: list[PlatformItem]) -> str: ...


def realize(golden, realizer, preference=EditionPolicy.default()):
    realized = []
    for e in golden.entries:
        if not e.verdict.admitted:
            continue
        if isinstance(e.item, Recording):
            pi = realizer.resolve(e.item)
            items = (pi,) if pi is not None else ()
            realized.append(RealizedEntry(e, items=items, compromises=()))
        elif isinstance(e.item, Album):
            effective_preference = e.edition if e.edition is not None else preference
            items_list, comps = realizer.resolve_album(e.item, effective_preference)
            realized.append(RealizedEntry(e, items=tuple(items_list), compromises=comps))
        else:
            realized.append(RealizedEntry(e, items=(), compromises=()))
    return Realization(golden.name, tuple(realized))
```

- [ ] **Step 5: Update the CLI formatter** (`cli.py`, replace the two `if e.compromise:` blocks at lines 49–50 and 54–55):

```python
        elif len(e.items) == 1:
            item = e.items[0]
            line = f"  ✓ {r.artist} — {r.title} → {item.ref}  [{item.quality.value}]"
            if e.compromises:
                line += "  [compromise: " + "; ".join(c.note for c in e.compromises) + "]"
            lines.append(line)
        else:
            line = f"  ✓ {r.artist} — {r.title} → {len(e.items)} tracks"
            if e.compromises:
                line += "  [compromise: " + "; ".join(c.note for c in e.compromises) + "]"
            lines.append(line)
```

- [ ] **Step 6: Update `tests/fakes.py::FakeRealizer`** — `resolve_album` default `return [], None` → `return [], ()`; update its docstring (`albums` maps title → `([PlatformItem, ...], tuple[Compromise, ...])`).

- [ ] **Step 7: Run the migrated tests, then the full offline suite.**

Run: `uv run pytest tests/core/test_realize.py tests/test_cli.py -v`
Expected: PASS
Run: `uv run pytest -m "not integration" -q`
Expected: PASS **except** the `tests/realize/test_tidal.py` `resolve_album` tests that still unpack a `str` compromise — those are fixed in Task 8. If the suite is red only there, that is expected at this step; proceed to Task 8 before the slice's final green.

> Note: `test_tidal.py`'s `resolve_album` tests call the **real** `TidalRealizer`, which still returns `str | None` until Task 8. Two of them (`test_resolve_album_drops_wrong_artist`, `test_resolve_album_returns_empty_when_nothing_matches`) assert `compromise is None` and still pass; the rest ignore the compromise. So the offline suite should in fact stay fully green here — but if any `test_tidal` assertion trips, it is resolved in Task 8.

- [ ] **Step 8: Commit.**

```bash
git add src/tidalist/core/realize.py src/tidalist/cli.py tests/fakes.py tests/core/test_realize.py tests/test_cli.py
git commit -m "feat(core): typed per-facet compromises; resolve_album returns Compromise tuple"
```

---

## Task 8: Rebuild `TidalRealizer.resolve_album` on `choose`

**Files:**
- Modify: `src/tidalist/realize/tidal.py`
- Test: `tests/realize/test_tidal.py`

**Interfaces:**
- Consumes: `PlatformCandidate`, `IdentityFacet`, `EditionFacet`, `choose` (from `core.fidelity`); `PlatformItem`, `MatchQuality` (from `core.realize`).
- Produces: `TidalRealizer.resolve_album(album, preference) -> tuple[list[PlatformItem], tuple[Compromise, ...]]`, selecting the same edition as before (behavior-preserving) and returning typed compromises.

- [ ] **Step 1: Migrate the two failing `resolve_album` tests** in `tests/realize/test_tidal.py`:
  - `test_resolve_album_drops_wrong_artist`: `assert compromise is None` → `assert compromise == ()`.
  - `test_resolve_album_returns_empty_when_nothing_matches`: `assert compromise is None` → `assert compromise == ()`.

- [ ] **Step 2: Run them to verify they fail.**

Run: `uv run pytest tests/realize/test_tidal.py -k "drops_wrong_artist or returns_empty_when_nothing" -v`
Expected: FAIL — the real `resolve_album` still returns `None`, so `compromise == ()` fails (and `()` is the new contract).

- [ ] **Step 3: Rebuild `resolve_album`.** Replace imports and the method in `tidal.py`:

```python
from ..core.realize import PlatformItem, MatchQuality
from ..core.fidelity import PlatformCandidate, IdentityFacet, EditionFacet, choose
```

(Remove the now-unused `from ..core.realize import EditionOption, choose_edition` import line.)

```python
    def resolve_album(self, album, preference):
        survivors = self._search_survivors(album)
        if not survivors:
            return [], ()
        anchor = survivors[0]
        # The discography gives the full edition set; fall back to the search survivors
        # when it is empty (so `editions` is always non-empty here).
        editions = self._platform.album_editions(anchor.id) or survivors
        candidates = [self._candidate(e, with_tracks=bool(album.tracklist)) for e in editions]
        facets = [IdentityFacet(), EditionFacet(preference)]
        chosen, comps = choose(album, candidates, facets)
        if chosen is None:
            return [], ()
        tracks = chosen.tracks or tuple(self._platform.album_tracks(TrackId(chosen.ref)))
        items = [_item(t, MatchQuality.STRONG) for t in tracks]
        return items, comps

    def _candidate(self, edition, with_tracks: bool) -> PlatformCandidate:
        tracks = tuple(self._platform.album_tracks(edition.id)) if with_tracks else ()
        return PlatformCandidate(ref=str(edition.id), title=edition.title,
                                 artists=edition.artists, year=edition.year, tracks=tracks)
```

(`TrackId` is already imported in `tidal.py`.)

- [ ] **Step 4: Run the `resolve_album` tests, including the Mr. Fantasy edition-selection test.**

Run: `uv run pytest tests/realize/test_tidal.py -v`
Expected: PASS — `test_resolve_album_prefers_edition_nearest_golden_tracklist` still resolves to the 10 `T1..T10` refs (IdentityFacet contributes 0 for all pre-filtered survivors; EditionFacet reproduces the prior argmin).

- [ ] **Step 5: Run the full offline suite.**

Run: `uv run pytest -m "not integration" -q`
Expected: PASS (293).

- [ ] **Step 6: Commit.**

```bash
git add src/tidalist/realize/tidal.py tests/realize/test_tidal.py
git commit -m "feat(realize): TidalRealizer.resolve_album selects editions via choose + facets"
```

---

## Task 9: Slice-1 verification (offline + live edition proof)

**Files:** none (verification only)

- [ ] **Step 1: Full offline suite.**

Run: `uv run pytest -m "not integration" -q`
Expected: PASS (293). No skips beyond the existing baseline.

- [ ] **Step 2: Live edition proof (needs Tidal creds; the behavior-preserving acceptance gate).**

Run: `uv run pytest tests/realize/test_edition_distance_live.py -v`
Expected: PASS — Traffic *Mr. Fantasy* still resolves to the 10-track original (album 639224), not the 22-track deluxe. (If creds are unavailable, record that this gate was deferred; do not claim it passed.)

- [ ] **Step 3: Update `TODO.md`** — note slice 1 (abstraction + edition migration) done; slices 2–4 of the uniform-realize work remain. Commit:

```bash
git add TODO.md
git commit -m "docs: uniform-realize slice 1 (facets + edition migration) landed"
```

---

## Subsequent slices (roadmap — each gets its own detailed plan when slice 1 lands the real shapes)

These are intentionally **not** broken into bite-sized tasks here; the concrete code depends on slice 1's landed types and on probing live tidalapi for the observation signals. Each will be planned via `superpowers:writing-plans` in its own session.

### Slice 2 — Recording facets + no-silent-substitution
- Add `PerformanceFacet` (recording): observe `performance` on candidates (distinct-ISRC identity + title markers like "live"/"live at"); emit `Compromise("performance", "studio", "live", …)` when the chosen take's performance differs from the golden's desired.
- Add `ReleaseClassFacet` (album): observe comp/live from title markers + identity; compromise when the chosen release's class differs from the golden's `traits`.
- Route `TidalRealizer.resolve` (recording) through `choose` over `[IdentityFacet, PerformanceFacet]`; build recording `PlatformCandidate`s from the ISRC lookup + search hits, observing performance. Change `Realizer.resolve` to return compromises (or keep `resolve` returning the item and surface compromises through a parallel return — decided in that slice's plan).
- Live acceptance: a studio-requested track whose studio ISRC is absent but a live take exists → substitutes + reports the performance compromise.

### Slice 3 — Track-level album fallback (most ambitious; live-fixture gated)
- When `_search_survivors` finds no edition clearing identity, assemble the canonical tracklist track-by-track: for each `TrackRef` in `golden.tracklist`, run the recording `choose` path to find that track anywhere (comp/live/other release). Emit `Compromise("album-source", …, "assembled from N releases")`; report still-unfound positions as a partial. Only zero tracks found → gap.
- Live fixture: Captain Beefheart — *Trout Mask Replica* (album absent on Tidal, many tracks present via compilations) → assembled-from-comps + reported missing positions, not a gap.

### Slice 4 — Quality-preference policy depth
- Flesh out `AudioFacet` into a specifiable policy (`EditionPreference`-shaped): original-source > comp, hi-res > lossy, popularity. Wire it as the lowest-weight facet so it only breaks distance-0 ties (superseding the slice-1 `ref` secondary key). Observe `source_kind`/`audio_quality`/`popularity` on candidates from tidalapi.
- Acceptance: same ISRC on the original album vs a comp → original; hi-res vs lossy → hi-res.
