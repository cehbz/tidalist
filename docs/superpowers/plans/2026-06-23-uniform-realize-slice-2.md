# Uniform Realize — Slice 2 (Recording Facets + No-Silent-Substitution) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make recording resolution facet-native: route `TidalRealizer.resolve` through `choose` over `[IdentityFacet, PerformanceFacet]`, observe each candidate's performance, prefer the matching take, and report a typed `Compromise` when it substitutes (no more silent live-for-studio swaps). `Realizer.resolve` returns compromises.

**Architecture:** Same ports-and-adapters pure DDD core. Slice 1 built the facet framework and used it for albums; slice 2 extends it to recordings. `IdentityFacet` gains a fuzzy closeness fallback (title/artist/duration) so it can rank search hits when ISRC doesn't decide; `PerformanceFacet` scores studio/live mismatch and emits the compromise. The adapter observes performance from track titles; scoring stays pure in `core/fidelity.py`.

**Tech Stack:** Python 3.12 (uv), stdlib-only core, `pytest`. Run via `uv run`.

## Global Constraints

- uv only; `uv run pytest -m "not integration"` (offline) and `uv run pytest` (with live, needs creds). `pythonpath=["src","."]`.
- Domain core (`core/`) is **pure**: no I/O, no third-party imports. Value objects `@dataclass(frozen=True, slots=True)`.
- Outbound deps are `typing.Protocol` ports; core imports no adapter.
- TDD red→green→refactor; the RED step must be a *failing assertion* (stub past any ImportError first), not a compile/import error.
- Structured errors; no bare `except`; no silent swallow in core.
- **Baseline at slice-2 start: 306 offline tests passing + 6 deselected** (branch `uniform-realize-slice-1` HEAD `989a3d8`).
- Album resolution stays behavior-preserving (Mr. Fantasy → 10-track). Slice 2 only changes the *recording* path and `IdentityFacet`'s *recording* branch; `IdentityFacet` for Albums still returns 0.
- Commit messages are pre-approved (shown per task). Each ends with the trailer:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

## Design notes (decisions approved 2026-06-23)

- **`IdentityFacet` revised.** Slice 1's `W_IDENTITY` ISRC-mismatch *cliff* is wrong for ranking recording search hits (a different-ISRC live take of the right song must not be nuked below a no-ISRC wrong song). ISRC becomes a **positive exact-match signal only**: equal ISRC → 0; otherwise **fuzzy closeness** over title (`W_FUZZY_TITLE`), artist (`W_FUZZY_ARTIST`), and duration (`W_FUZZY_DUR`/sec). `W_IDENTITY` is removed. Album branch unchanged (returns 0).
- **Recording weight ladder:** `W_FUZZY_TITLE = W_FUZZY_ARTIST = 1000` ≫ `W_PERFORMANCE = 100` ≫ `W_FUZZY_DUR = 1`/sec. Getting the right song dominates studio-vs-live, which dominates the per-second duration tiebreak. All well below any album-only weights (those facets no-op on recordings).
- **`PlatformCandidate` gains `duration_s`** for closeness. The weak *album* sub-signal of the old `_closeness` is dropped (no album field on `PlatformCandidate`).
- **`Realizer.resolve` contract flips** to `tuple[PlatformItem | None, tuple[Compromise, ...]]`, uniform with `resolve_album`. `realize()`, both fakes, and the recording tests update.
- **Best-effort observation:** performance is observed from track-title markers (`(live`, ` - live`, `unplugged`, …) → `LIVE`, else `UNKNOWN`. `PerformanceFacet` no-ops when either side is `UNKNOWN` (unobserved ⇒ no penalty, no compromise).
- **Scope:** `ReleaseClassFacet` is **deferred to slice 3** (it would no-op in slice 2, since editions of one release-group share their class; its teeth are in slice 3's cross-release track assembly).

## File structure

- **Modify `src/tidalist/core/fidelity.py`** — add `PlatformCandidate.duration_s`; add `W_PERFORMANCE`, `PerformanceFacet`; add `W_FUZZY_*` + `recording_artist_match`; revise `IdentityFacet`; remove `W_IDENTITY`.
- **Modify `src/tidalist/realize/tidal.py`** — rewrite `resolve` facet-native; add `_track_candidate`/`_observe_performance`/`_item_from_candidate`/`_quality_for`; remove dead `_closeness`/`_album_match`/`_quality`/`_artist_match`; update imports.
- **Modify `src/tidalist/core/realize.py`** — `Realizer.resolve` return type; `realize()` recording branch.
- **Modify `tests/fakes.py`** and **`tests/core/test_realize.py`** — fakes' `resolve` returns a tuple.
- **Modify tests** — `tests/core/test_fidelity.py` (facet tests), `tests/realize/test_tidal.py` (resolve tests + a deterministic no-silent-sub test).

---

## Task 1: PlatformCandidate carries observed duration

**Files:** Modify `src/tidalist/core/fidelity.py`; Test `tests/core/test_fidelity.py`

**Interfaces:**
- Produces: `PlatformCandidate.duration_s: int | None = None` (new field; all construction is keyword-based, so position is free — place it after `year`).

- [ ] **Step 1: Write the failing test** (append to `tests/core/test_fidelity.py`):

```python
def test_platform_candidate_carries_duration():
    c = PlatformCandidate(ref="t1", title="Glad", duration_s=386)
    assert c.duration_s == 386
```

Also extend the existing `test_platform_candidate_defaults_are_observation_unknowns` to assert the new default:

```python
    assert c.duration_s is None
```

- [ ] **Step 2: Run to verify the new assertions fail.**

Run: `uv run pytest tests/core/test_fidelity.py -k platform_candidate -v`
Expected: FAIL (`TypeError: unexpected keyword 'duration_s'` once the keyword is used; if that reads as an error rather than a failure, the field simply doesn't exist yet — add it next).

- [ ] **Step 3: Add the field** in `PlatformCandidate`, after `year`:

```python
    year: int | None = None
    duration_s: int | None = None
    tracks: tuple[Track, ...] = ()
```

- [ ] **Step 4: Run to verify pass.**

Run: `uv run pytest tests/core/test_fidelity.py -k platform_candidate -v`
Expected: PASS

- [ ] **Step 5: Commit.**

```bash
git add src/tidalist/core/fidelity.py tests/core/test_fidelity.py
git commit -F <msg>   # feat(core): PlatformCandidate carries observed duration  (+ trailer)
```

---

## Task 2: PerformanceFacet

**Files:** Modify `src/tidalist/core/fidelity.py`; Test `tests/core/test_fidelity.py`

**Interfaces:**
- Consumes: `Recording`, `Performance`, `Album`, `Compromise`, `PlatformCandidate`.
- Produces: `W_PERFORMANCE = 100`; `PerformanceFacet(name="performance", weight=1.0)`. `distance` → `0.0` unless `golden` is a `Recording` with a known `performance` and `cand.performance` is known; then `0.0` if equal else `W_PERFORMANCE`. `compromise` → `None` unless a known mismatch; then `Compromise("performance", golden.performance.value, cand.performance.value, f"{golden.performance.value} take unavailable; used a {cand.performance.value} version")`.

- [ ] **Step 1: Write the failing tests.**

```python
def test_performance_facet_no_op_on_albums():
    from tidalist.core.fidelity import PerformanceFacet
    g = Album(artist="Traffic", title="Mr. Fantasy")
    cand = PlatformCandidate(ref="a", title="Mr. Fantasy")
    assert PerformanceFacet().distance(g, cand) == 0.0
    assert PerformanceFacet().compromise(g, cand) is None


def test_performance_facet_no_penalty_when_observation_unknown():
    from tidalist.core.fidelity import PerformanceFacet
    g = Recording(artist="t", title="Glad", performance=Performance.STUDIO)
    cand = PlatformCandidate(ref="x", title="Glad")  # performance UNKNOWN
    assert PerformanceFacet().distance(g, cand) == 0.0
    assert PerformanceFacet().compromise(g, cand) is None


def test_performance_facet_match_is_zero_no_compromise():
    from tidalist.core.fidelity import PerformanceFacet
    g = Recording(artist="t", title="Glad", performance=Performance.STUDIO)
    cand = PlatformCandidate(ref="x", title="Glad", performance=Performance.STUDIO)
    assert PerformanceFacet().distance(g, cand) == 0.0
    assert PerformanceFacet().compromise(g, cand) is None


def test_performance_facet_mismatch_penalizes_and_reports():
    from tidalist.core.fidelity import PerformanceFacet, W_PERFORMANCE
    g = Recording(artist="t", title="Glad", performance=Performance.STUDIO)
    cand = PlatformCandidate(ref="x", title="Glad (Live)", performance=Performance.LIVE)
    assert PerformanceFacet().distance(g, cand) == W_PERFORMANCE
    comp = PerformanceFacet().compromise(g, cand)
    assert comp is not None
    assert comp.facet == "performance"
    assert comp.desired == "studio" and comp.used == "live"
    assert comp.note == "studio take unavailable; used a live version"
```

- [ ] **Step 2: Run to verify they fail** (add a stub `PerformanceFacet` whose `distance` returns `0.0`/`compromise` returns `None` so the mismatch assertions fail, not import).

Run: `uv run pytest tests/core/test_fidelity.py -k performance_facet -v`
Expected: FAIL on the mismatch test's distance/compromise assertions.

- [ ] **Step 3: Implement** (place after `IdentityFacet`):

```python
W_PERFORMANCE = 100   # studio/live mismatch penalty for recordings


@dataclass(frozen=True, slots=True)
class PerformanceFacet:
    """Penalizes a recording whose observed performance differs from the golden's
    desired performance, and reports it. No-ops on albums and when either performance
    is UNKNOWN (unobserved ⇒ best-effort, no penalty)."""
    name: str = "performance"
    weight: float = 1.0

    def distance(self, golden, cand) -> float:
        if not isinstance(golden, Recording):
            return 0.0
        if golden.performance is Performance.UNKNOWN or cand.performance is Performance.UNKNOWN:
            return 0.0
        return 0.0 if cand.performance == golden.performance else W_PERFORMANCE

    def compromise(self, golden, cand):
        if not isinstance(golden, Recording):
            return None
        if golden.performance is Performance.UNKNOWN or cand.performance is Performance.UNKNOWN:
            return None
        if cand.performance == golden.performance:
            return None
        return Compromise("performance", golden.performance.value, cand.performance.value,
                          f"{golden.performance.value} take unavailable; "
                          f"used a {cand.performance.value} version")
```

- [ ] **Step 4: Run to verify pass + full offline suite.**

Run: `uv run pytest tests/core/test_fidelity.py -k performance_facet -v` → PASS
Run: `uv run pytest -m "not integration" -q` → PASS

- [ ] **Step 5: Commit.**

```bash
git add src/tidalist/core/fidelity.py tests/core/test_fidelity.py
git commit -F <msg>   # feat(core): PerformanceFacet — studio/live mismatch distance + compromise  (+ trailer)
```

---

## Task 3: IdentityFacet fuzzy closeness for recordings

**Files:** Modify `src/tidalist/core/fidelity.py`; Test `tests/core/test_fidelity.py`

**Interfaces:**
- Produces: `W_FUZZY_TITLE = 1000`, `W_FUZZY_ARTIST = 1000`, `W_FUZZY_DUR = 1`; `recording_artist_match(recording: Recording, artists: tuple[str, ...]) -> bool`; revised `IdentityFacet.distance`. **Removes** `W_IDENTITY`.
- Revised `IdentityFacet.distance(golden, cand)`: Album → `0.0`; Recording with equal present ISRCs → `0.0`; else `W_FUZZY_TITLE·[title mismatch] + W_FUZZY_ARTIST·[artist mismatch] + W_FUZZY_DUR·|Δduration|`.

- [ ] **Step 1: Migrate/replace the IdentityFacet tests.** In `tests/core/test_fidelity.py`:
  - Change the import line to drop `W_IDENTITY, W_MARKER` and add the fuzzy weights:
    ```python
    from tidalist.core.fidelity import (
        Compromise, PlatformCandidate, realize_distance, choose,
        IdentityFacet, W_FUZZY_TITLE, W_FUZZY_ARTIST, W_FUZZY_DUR,
        EditionFacet, edition_distance,
    )
    ```
  - **Delete** `test_identity_dominates_marker`.
  - **Keep** `test_identity_recording_isrc_match_is_zero` and `test_identity_album_is_zero` unchanged.
  - **Replace** `test_identity_recording_isrc_mismatch_is_w_identity` and `test_identity_recording_unknown_isrc_is_zero` with:
    ```python
    def test_identity_recording_isrc_mismatch_falls_back_to_fuzzy():
        # Different ISRC but identical title/artist/duration -> fuzzy match -> 0 (no cliff).
        g = Recording(artist="Traffic", title="Glad", isrc=ISRC("GB1"), duration_s=200)
        cand = PlatformCandidate(ref="t2", title="Glad", isrc=ISRC("GB2"),
                                 artists=("Traffic",), duration_s=200)
        assert IdentityFacet().distance(g, cand) == 0.0


    def test_identity_recording_fuzzy_full_match_is_zero():
        g = Recording(artist="Traffic", title="Glad", duration_s=200)   # no ISRC
        cand = PlatformCandidate(ref="t3", title="Glad", artists=("Traffic",), duration_s=200)
        assert IdentityFacet().distance(g, cand) == 0.0


    def test_identity_recording_title_mismatch_adds_fuzzy_title():
        g = Recording(artist="Traffic", title="Glad", duration_s=200)
        cand = PlatformCandidate(ref="x", title="Glad Rag Doll", artists=("Traffic",), duration_s=200)
        assert IdentityFacet().distance(g, cand) == W_FUZZY_TITLE


    def test_identity_recording_artist_mismatch_adds_fuzzy_artist():
        g = Recording(artist="Traffic", title="Glad", duration_s=200)
        cand = PlatformCandidate(ref="x", title="Glad", artists=("Other Band",), duration_s=200)
        assert IdentityFacet().distance(g, cand) == W_FUZZY_ARTIST


    def test_identity_recording_duration_delta_adds_fuzzy_dur():
        g = Recording(artist="Traffic", title="Glad", duration_s=386)
        cand = PlatformCandidate(ref="x", title="Glad", artists=("Traffic",), duration_s=380)
        assert IdentityFacet().distance(g, cand) == W_FUZZY_DUR * 6
    ```

- [ ] **Step 2: Run to verify the new/changed tests fail** (the revised distance and missing constants).

Run: `uv run pytest tests/core/test_fidelity.py -k identity -v`
Expected: FAIL on the fuzzy assertions (old `IdentityFacet` returns `W_IDENTITY`/`0.0`, and `W_FUZZY_*` don't exist — add them next).

- [ ] **Step 3: Implement.** Remove the `W_IDENTITY` block (the three lines defining it + its comment). Add the fuzzy weights near the other weight constants:

```python
# Fuzzy-closeness weights for recording identity when ISRC doesn't decide.
# title/artist dominate W_PERFORMANCE (100); duration is the finest tiebreak.
W_FUZZY_TITLE  = 1000
W_FUZZY_ARTIST = 1000
W_FUZZY_DUR    = 1
```

Add the helper (near `_norm`):

```python
def recording_artist_match(recording: Recording, artists: tuple[str, ...]) -> bool:
    """True if a performer of the recording overlaps the candidate's artists."""
    performers = {_norm(c.artist) for c in recording.credits if c.role == "performer"}
    performers.add(_norm(recording.artist))
    return any(p and any(p in _norm(a) or _norm(a) in p for a in artists)
               for p in performers)
```

Replace `IdentityFacet.distance`:

```python
    def distance(self, golden, cand) -> float:
        if not isinstance(golden, Recording):
            return 0.0
        # Exact ISRC is a positive identity signal.
        if golden.isrc is not None and cand.isrc is not None and golden.isrc == cand.isrc:
            return 0.0
        # Otherwise fuzzy closeness: title / artist / duration.
        d = 0.0
        if _norm(golden.title) != _norm(cand.title):
            d += W_FUZZY_TITLE
        if not recording_artist_match(golden, cand.artists):
            d += W_FUZZY_ARTIST
        d += W_FUZZY_DUR * abs((golden.duration_s or 0) - (cand.duration_s or 0))
        return d
```

(Update the `IdentityFacet` docstring to describe the fuzzy fallback; `compromise` still returns `None`.)

- [ ] **Step 4: Run to verify pass + full offline suite.**

Run: `uv run pytest tests/core/test_fidelity.py -k identity -v` → PASS
Run: `uv run pytest -m "not integration" -q` → PASS (confirm `W_IDENTITY` removal broke no import — only `test_fidelity.py` referenced it).

- [ ] **Step 5: Commit.**

```bash
git add src/tidalist/core/fidelity.py tests/core/test_fidelity.py
git commit -F <msg>   # feat(core): IdentityFacet fuzzy closeness for recordings (ISRC as positive signal)  (+ trailer)
```

---

## Task 4: Recording resolution via choose; resolve reports compromises

**Files:** Modify `src/tidalist/realize/tidal.py`, `src/tidalist/core/realize.py`, `tests/fakes.py`, `tests/core/test_realize.py`, `tests/realize/test_tidal.py`

**Interfaces:**
- Consumes: `IdentityFacet`, `PerformanceFacet`, `choose`, `recording_artist_match`, `PlatformCandidate` (core.fidelity).
- Produces: `Realizer.resolve(recording) -> tuple[PlatformItem | None, tuple[Compromise, ...]]`; `TidalRealizer.resolve` facet-native; `realize()` recording branch unpacks compromises; both fakes' `resolve` return a tuple.

- [ ] **Step 1: Find every `resolve` caller** so none is missed:

Run: `grep -rn "\.resolve(" src/ tests/ | grep -v resolve_album`
Expected callers to update: `core/realize.py::realize`, `tests/fakes.py::FakeRealizer`, `tests/core/test_realize.py::_FakeRealizer`, `tests/realize/test_tidal.py` (5 resolve tests). Note any others the grep finds (e.g. `tests/test_fakes.py`) and update them too.

- [ ] **Step 2: Migrate the failing tests first.**
  - In `tests/realize/test_tidal.py`, unpack the tuple in all five resolve tests:
    ```python
    def test_resolve_by_isrc_takes_precedence_with_isrc_quality():
        target = _track("T-isrc", isrc=ISRC("GB1"))
        cat = FakePlatform([target, _track("T-decoy")])
        item, _ = TidalRealizer(cat).resolve(_rec(isrc=ISRC("GB1")))
        assert item.ref == "T-isrc" and item.quality is MatchQuality.ISRC

    def test_resolve_falls_back_to_closest_search_hit():
        right = _track("T-right", title="Glad", artists=("Traffic",))
        looser = _track("T-loose", title="Glad Rag Doll", artists=("Traffic",))
        cat = FakePlatform([looser, right])
        item, _ = TidalRealizer(cat).resolve(_rec())
        assert item.ref == "T-right" and item.quality is MatchQuality.STRONG

    def test_resolve_returns_none_when_search_finds_nothing():
        item, comps = TidalRealizer(FakePlatform([])).resolve(_rec())
        assert item is None and comps == ()

    def test_resolve_prefers_closer_duration_among_equal_hits():
        a = _track("T-a", title="Glad", artists=("Traffic",), duration_s=200)
        b = _track("T-b", title="Glad", artists=("Traffic",), duration_s=386)
        cat = FakePlatform([a, b])
        item, _ = TidalRealizer(cat).resolve(_rec(duration_s=386))
        assert item.ref == "T-b"

    def test_resolve_marks_a_title_mismatch_weak():
        only = _track("T-x", title="Glad Rag Doll", artists=("Traffic",))
        item, _ = TidalRealizer(FakePlatform([only])).resolve(_rec())
        assert item.ref == "T-x" and item.quality is MatchQuality.WEAK
    ```
  - Add a deterministic no-silent-substitution test to `tests/realize/test_tidal.py`:
    ```python
    def test_resolve_substitutes_a_live_take_and_reports_the_compromise():
        from tidalist.core.recording import Performance
        rec = Recording(artist="Traffic", title="Dear Mr. Fantasy",
                        performance=Performance.STUDIO,
                        credits=(Credit("Traffic", "performer"),))
        live = _track("T-live", title="Dear Mr. Fantasy (Live)", artists=("Traffic",))
        cat = FakePlatform([live])
        item, comps = TidalRealizer(cat).resolve(rec)
        assert item.ref == "T-live"
        assert len(comps) == 1
        assert comps[0].facet == "performance"
        assert comps[0].note == "studio take unavailable; used a live version"
    ```
  - In `tests/fakes.py` (`FakeRealizer`) and `tests/core/test_realize.py` (`_FakeRealizer`), the `resolve` body and the realize() tests need the tuple shape (Step 4).

- [ ] **Step 3: Run the migrated tests to verify they fail.**

Run: `uv run pytest tests/realize/test_tidal.py -k resolve -v`
Expected: FAIL — current `resolve` returns a bare `PlatformItem`, so tuple-unpacking and the compromise assertions fail.

- [ ] **Step 4: Implement.**

In `src/tidalist/core/realize.py`, update the protocol and `realize()`:

```python
    def resolve(self, recording: Recording) -> tuple[PlatformItem | None, tuple[Compromise, ...]]: ...
```

```python
        if isinstance(e.item, Recording):
            pi, comps = realizer.resolve(e.item)
            items = (pi,) if pi is not None else ()
            realized.append(RealizedEntry(e, items=items, compromises=comps))
```

In `src/tidalist/realize/tidal.py`, update imports and rewrite `resolve`; add helpers; delete `_closeness`, `_album_match`, `_quality`, `_artist_match`:

```python
from ..core.recording import Recording, Performance
from ..core.realize import PlatformItem, MatchQuality
from ..core.fidelity import (
    PlatformCandidate, IdentityFacet, EditionFacet, PerformanceFacet, choose,
    recording_artist_match, Compromise,
)
```

```python
    def resolve(self, recording: Recording) -> tuple[PlatformItem | None, tuple[Compromise, ...]]:
        if recording.isrc is not None:
            track = self._platform.track_by_isrc(recording.isrc)
            if track is not None:
                return _item(track, MatchQuality.ISRC), ()
        hits = self._platform.search_tracks(_query(recording))
        candidates = [_track_candidate(t) for t in hits]
        if not candidates:
            return None, ()
        chosen, comps = choose(recording, candidates, [IdentityFacet(), PerformanceFacet()])
        if chosen is None:
            return None, ()
        return _item_from_candidate(chosen, _quality_for(recording, chosen)), comps
```

Module-level helpers (replace the deleted `_closeness`/`_album_match`/`_quality`/`_artist_match`):

```python
_LIVE_MARKERS = ("(live", "[live", " live at ", " - live", "live in ", "live from", "unplugged")


def _observe_performance(title: str) -> Performance:
    t = title.casefold()
    return Performance.LIVE if any(m in t for m in _LIVE_MARKERS) else Performance.UNKNOWN


def _track_candidate(track: Track) -> PlatformCandidate:
    return PlatformCandidate(
        ref=str(track.id), title=track.title, artists=track.artists,
        isrc=track.isrc, duration_s=track.duration_s,
        performance=_observe_performance(track.title),
    )


def _item_from_candidate(cand: PlatformCandidate, quality: MatchQuality) -> PlatformItem:
    return PlatformItem(ref=cand.ref, title=cand.title, artists=cand.artists,
                        isrc=cand.isrc, quality=quality)


def _quality_for(recording: Recording, cand: PlatformCandidate) -> MatchQuality:
    title_ok = _norm(recording.title) == _norm(cand.title)
    artist_ok = recording_artist_match(recording, cand.artists)
    return MatchQuality.STRONG if title_ok and artist_ok else MatchQuality.WEAK
```

In `tests/fakes.py` (`FakeRealizer.resolve`) and `tests/core/test_realize.py` (`_FakeRealizer.resolve`):

```python
    def resolve(self, recording):
        return self._by_title.get(recording.title.casefold()), ()
```

(Any other caller the Step-1 grep surfaced, e.g. in `tests/test_fakes.py`, unpacks `item, _ = …` similarly.)

- [ ] **Step 5: Run the migrated tests, then the full offline suite.**

Run: `uv run pytest tests/realize/test_tidal.py tests/core/test_realize.py -v` → PASS
Run: `uv run pytest -m "not integration" -q` → PASS (Mr. Fantasy album path untouched; recording path now facet-native).

- [ ] **Step 6: Commit.**

```bash
git add src/tidalist/realize/tidal.py src/tidalist/core/realize.py tests/fakes.py tests/core/test_realize.py tests/realize/test_tidal.py
git commit -F <msg>   # feat(realize): recording resolution via choose; resolve reports compromises  (+ trailer)
```

---

## Task 5: Live no-silent-substitution confirmation (best-effort)

**Files:** Create `tests/realize/test_no_silent_sub_live.py` (`@pytest.mark.integration`)

The deterministic behavior is already proven offline in Task 4. This task adds a *best-effort* live confirmation against real Tidal. If a clean, stable fixture cannot be found (a song whose studio ISRC is genuinely absent from Tidal while a live take is searchable), **do not fake a pass** — report the task as DONE_WITH_CONCERNS noting the live fixture was deferred, and skip the commit.

- [ ] **Step 1: Probe for a fixture.** Using the live config, find a `Recording` (studio, with an ISRC that returns `None` from `track_by_isrc`) whose title search returns a live take. Document the chosen artist/title in the test.

- [ ] **Step 2: Write the integration test** asserting `resolve` returns an item and a `performance` compromise:

```python
import pytest
# ... build a real TidalPlatform via the app config (mirror tests/realize/test_tidal_live.py setup) ...

@pytest.mark.integration
def test_studio_absent_recording_substitutes_live_with_compromise(...):
    item, comps = realizer.resolve(studio_recording)
    assert item is not None
    assert any(c.facet == "performance" for c in comps)
```

- [ ] **Step 3: Run it live.**

Run: `uv run pytest tests/realize/test_no_silent_sub_live.py -v`
Expected: PASS. If no stable fixture exists, report DONE_WITH_CONCERNS (deferred) and do not commit.

- [ ] **Step 4: Commit (only if the live test is real and green).**

```bash
git add tests/realize/test_no_silent_sub_live.py
git commit -F <msg>   # test(realize): live — studio-absent recording substitutes a live take, reports the compromise  (+ trailer)
```

---

## Task 6: Slice-2 verification + landed docs

**Files:** Modify `TODO.md`

- [ ] **Step 1: Full offline suite.**

Run: `uv run pytest -m "not integration" -q`
Expected: PASS (306 + the slice-2 net-new tests; no deselected change beyond the existing 6 + any live tests added).

- [ ] **Step 2: Update `TODO.md`** — note slice 2 landed (recording facets + no-silent-substitution); slices 3–4 remain. Commit:

```bash
git add TODO.md
git commit -F <msg>   # docs: uniform-realize slice 2 (recording facets + no-silent-substitution) landed  (+ trailer)
```

*(The whole-branch review is run by the controller after this task, not as a commit.)*

---

## Subsequent slices (roadmap — own plans when these land)

- **Slice 3 — Track-level album fallback** (most ambitious; live fixture Captain Beefheart *Trout Mask Replica*): per-track assembly when no edition clears identity; `Compromise("album-source", …)` + missing-positions partial. Adds `ReleaseClassFacet` (observe comp/live on the assembled-from releases). Reuses the recording `choose` path built in slice 2.
- **Slice 4 — Quality-preference policy depth:** flesh `AudioFacet` into a specifiable policy (original-source > comp, hi-res > lossy, popularity), superseding `choose`'s `ref` tiebreak.
