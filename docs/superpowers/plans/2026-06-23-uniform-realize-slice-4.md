# Uniform Realize — Slice 4 (Audio-Quality Tiebreak) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When recording candidates tie on the higher fidelity facets (identity/performance), break the tie by a **specifiable audio-quality preference** (hi-res > lossy, then more popular) instead of the arbitrary `ref` key — making `choose`'s deterministic tiebreak *meaningful*. Quality decides only on a genuine tie; `ref` stays the final determinism backstop.

**Architecture:** Extends slice 1's design — the deterministic tiebreak already lives in `choose`'s *secondary sort key* (`c.ref`). Slice 4 makes that key quality-aware via an optional `tiebreak` parameter and a `QualityPreference` policy. This is a **lexicographic** tiebreak (no summed "AudioFacet", no magnitude-tuned weight): quality acts only when `realize_distance` ties exactly. Core `Track` gains observed `audio_quality` + `popularity`.

**Tech Stack:** Python 3.12 (uv), stdlib-only core, `pytest`. Run via `uv run`.

## Global Constraints

- uv only; `uv run pytest -m "not integration"`. Domain core stays pure (no I/O, no third-party imports); value objects frozen+slots.
- TDD red→green; RED is a failing assertion (stub past ImportError first).
- **Baseline at slice-4 start: 323 offline passing + 7 deselected** (branch `uniform-realize-slice-3` HEAD `d764832`).
- Existing `choose` callers (album `resolve_album`, `choose_edition`) keep the plain `ref` tiebreak — the new `tiebreak` parameter defaults to the current behavior. Mr. Fantasy stays green.
- Commit messages are pre-approved (shown per task). Each ends with:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

## Design notes (decisions approved 2026-06-23)

- **Lexicographic tiebreak, not a summed facet.** A summed lowest-weight facet can't be a clean tiebreak with continuous higher-facet distances (its weight would have to be hand-tuned below a ~1-second duration difference — a magnitude-fragility smell). Instead the quality preference is `choose`'s secondary sort key, before the `ref` backstop: `min(c, key=(realize_distance, quality_key(c), ref))`. Quality decides only on an exact `realize_distance` tie (the "same track, two qualities" case); never overrides a real higher-facet difference. No magnitude tuning.
- **Scope: hi-res + popularity** (robustly observable from tidalapi: `track.audio_quality`, `track.popularity`). **`source_kind` (original > comp) is deferred** to the rich-metadata backend — title heuristics for compilation detection would be unreliable. The `QualityPreference` framework leaves a clean slot for it.
- **Recording path only this slice.** `Track` carries quality, so the recording `resolve` applies it. The album-edition tiebreak (and `PlatformAlbum` carrying quality) is a follow-on.

## File structure

- **Modify `src/tidalist/core/catalog.py`** — `Track` gains `audio_quality: str | None`, `popularity: int | None`.
- **Modify `src/tidalist/tidal/platform.py`** — `track_from_tidal` observes both from the tidalapi object.
- **Modify `src/tidalist/core/fidelity.py`** — add `QualityPreference` + `_audio_rank`; give `choose` an optional `tiebreak` parameter.
- **Modify `src/tidalist/realize/tidal.py`** — `_track_candidate` populates the two fields; `resolve` passes the quality tiebreak.
- **Tests** — `tests/core/test_catalog.py`, `tests/tidal/test_mapping.py`, `tests/core/test_fidelity.py`, `tests/realize/test_tidal.py`.

---

## Task 1: Track carries observed audio quality and popularity

**Files:** Modify `src/tidalist/core/catalog.py`, `src/tidalist/tidal/platform.py`; Test `tests/core/test_catalog.py`, `tests/tidal/test_mapping.py`

**Interfaces:**
- Produces: `Track.audio_quality: str | None = None`, `Track.popularity: int | None = None`; `track_from_tidal` observes `getattr(t, "audio_quality", None)` and `getattr(t, "popularity", None)`.

- [ ] **Step 1: Write the failing tests.** In `tests/core/test_catalog.py`:

```python
def test_track_carries_audio_quality_and_popularity():
    from tidalist.core.catalog import Track
    from tidalist.core.identifiers import TrackId
    t = Track(id=TrackId("1"), title="Glad", artists=("Traffic",),
              audio_quality="HI_RES_LOSSLESS", popularity=72)
    assert t.audio_quality == "HI_RES_LOSSLESS"
    assert t.popularity == 72


def test_track_audio_quality_and_popularity_default_none():
    from tidalist.core.catalog import Track
    from tidalist.core.identifiers import TrackId
    t = Track(id=TrackId("1"), title="Glad", artists=("Traffic",))
    assert t.audio_quality is None and t.popularity is None
```

In `tests/tidal/test_mapping.py` (read the file first to match its existing fake-tidalapi-object style — likely a `SimpleNamespace`), add a test that `track_from_tidal` observes both fields, e.g.:

```python
def test_track_from_tidal_observes_audio_quality_and_popularity():
    from types import SimpleNamespace
    from tidalist.tidal.platform import track_from_tidal
    t = SimpleNamespace(id=1, name="Glad", artists=[SimpleNamespace(name="Traffic")],
                        isrc=None, album=SimpleNamespace(name="A", year=1970),
                        tidal_release_date=None, duration=386,
                        audio_quality="LOSSLESS", popularity=50)
    track = track_from_tidal(t)
    assert track.audio_quality == "LOSSLESS" and track.popularity == 50
```

- [ ] **Step 2: Run to verify they fail.**

Run: `uv run pytest tests/core/test_catalog.py -k "audio_quality or popularity" tests/tidal/test_mapping.py -k "audio_quality" -v`
Expected: FAIL (`TypeError: unexpected keyword 'audio_quality'` once used — add the fields; if it reads as an error, the field is simply missing).

- [ ] **Step 3: Implement.** In `core/catalog.py`, add to `Track` after `duration_s`:

```python
    duration_s: int | None = None
    audio_quality: str | None = None
    popularity: int | None = None
```

In `tidal/platform.py` `track_from_tidal`, add the two observations:

```python
        duration_s=getattr(t, "duration", None),
        audio_quality=getattr(t, "audio_quality", None),
        popularity=getattr(t, "popularity", None),
    )
```

- [ ] **Step 4: Run to verify pass + full offline suite.**

Run: `uv run pytest tests/core/test_catalog.py tests/tidal/test_mapping.py -v` → PASS
Run: `uv run pytest -m "not integration" -q` → PASS

- [ ] **Step 5: Commit.**

```bash
git add src/tidalist/core/catalog.py src/tidalist/tidal/platform.py tests/core/test_catalog.py tests/tidal/test_mapping.py
git commit -F <msg>   # feat(core): Track carries observed audio quality and popularity  (+ trailer)
```

---

## Task 2: audio-quality tiebreak in choose + QualityPreference

**Files:** Modify `src/tidalist/core/fidelity.py`; Test `tests/core/test_fidelity.py`

**Interfaces:**
- Produces:
  - `QualityPreference(prefer_hires: bool = True, prefer_popular: bool = True)` with `tiebreak(cand) -> tuple` returning a sort key (lower is better): higher audio rank and higher popularity sort first.
  - `_audio_rank(q: str | None) -> int` (low=0, high=1, lossless=2, hi_res / hi_res_lossless / master / max = 3; unknown = 0).
  - `choose(golden, candidates, facets, tiebreak=None)` — when `tiebreak` is None, the secondary key is `c.ref` (unchanged); otherwise the key is `(realize_distance(...), tiebreak(c))`. Callers that want quality pass `tiebreak=lambda c: (pref.tiebreak(c), c.ref)`.

- [ ] **Step 1: Write the failing tests.**

```python
def test_quality_preference_ranks_hires_then_popularity():
    from tidalist.core.fidelity import QualityPreference, PlatformCandidate
    pref = QualityPreference()
    hi = PlatformCandidate(ref="hi", title="t", audio_quality="HI_RES_LOSSLESS", popularity=10)
    lo = PlatformCandidate(ref="lo", title="t", audio_quality="LOW", popularity=99)
    # hi-res dominates popularity: hi sorts before lo (smaller tiebreak tuple).
    assert pref.tiebreak(hi) < pref.tiebreak(lo)


def test_quality_preference_popularity_breaks_equal_quality():
    from tidalist.core.fidelity import QualityPreference, PlatformCandidate
    pref = QualityPreference()
    a = PlatformCandidate(ref="a", title="t", audio_quality="LOSSLESS", popularity=80)
    b = PlatformCandidate(ref="b", title="t", audio_quality="LOSSLESS", popularity=20)
    assert pref.tiebreak(a) < pref.tiebreak(b)   # higher popularity first


def test_choose_quality_tiebreak_picks_hires_on_a_tie():
    from tidalist.core.fidelity import QualityPreference, PlatformCandidate, choose
    from tidalist.core.recording import Recording
    g = Recording(artist="a", title="t")
    pref = QualityPreference()
    lossy = PlatformCandidate(ref="lossy", title="t", audio_quality="LOW")
    hires = PlatformCandidate(ref="hires", title="t", audio_quality="HI_RES_LOSSLESS")
    # No facets => realize_distance 0 for both => the quality tiebreak decides.
    chosen, _ = choose(g, [lossy, hires], [], tiebreak=lambda c: (pref.tiebreak(c), c.ref))
    assert chosen.ref == "hires"


def test_choose_default_tiebreak_unchanged_uses_ref():
    from tidalist.core.fidelity import PlatformCandidate, choose
    from tidalist.core.recording import Recording
    g = Recording(artist="a", title="t")
    a = PlatformCandidate(ref="a", title="t")
    b = PlatformCandidate(ref="b", title="t")
    assert choose(g, [b, a], [])[0].ref == "a"   # default ref tiebreak still wins
```

- [ ] **Step 2: Run to verify they fail** (add a `QualityPreference` stub + a no-op `tiebreak` param so the tests RUN, then implement).

Run: `uv run pytest tests/core/test_fidelity.py -k "quality or tiebreak" -v`
Expected: FAIL on the ranking/selection assertions.

- [ ] **Step 3: Implement** in `core/fidelity.py`:

```python
_QUALITY_RANK = {"low": 0, "high": 1, "lossless": 2,
                 "hi_res": 3, "hi_res_lossless": 3, "master": 3, "max": 3}


def _audio_rank(quality: str | None) -> int:
    return _QUALITY_RANK.get((quality or "").casefold(), 0)


@dataclass(frozen=True, slots=True)
class QualityPreference:
    """A specifiable quality tiebreak: prefer hi-res, then more popular. The distance-0
    quality layer — it breaks ties below every fidelity facet, never overriding one."""
    prefer_hires: bool = True
    prefer_popular: bool = True

    def tiebreak(self, cand) -> tuple:
        """Sort key, lower is better: higher audio rank and higher popularity first."""
        hires = -_audio_rank(cand.audio_quality) if self.prefer_hires else 0
        popular = -(cand.popularity or 0) if self.prefer_popular else 0
        return (hires, popular)
```

Change `choose` to accept the optional tiebreak:

```python
def choose(golden, candidates, facets, tiebreak=None):
    """Pick the candidate of minimum realize_distance; break ties by `tiebreak`
    (default: the candidate ref, for determinism); return it plus the winner's
    compromises."""
    if not candidates:
        return None, ()
    second = tiebreak if tiebreak is not None else (lambda c: c.ref)
    chosen = min(candidates, key=lambda c: (realize_distance(golden, c, facets), second(c)))
    comps = tuple(
        c for c in (f.compromise(golden, chosen) for f in facets) if c is not None
    )
    return chosen, comps
```

- [ ] **Step 4: Run the new tests + the full offline suite** (confirm existing `choose`/`choose_edition`/`resolve_album` tests stay green — they don't pass `tiebreak`, so the `ref` default preserves behavior).

Run: `uv run pytest tests/core/test_fidelity.py -v` → PASS
Run: `uv run pytest -m "not integration" -q` → PASS

- [ ] **Step 5: Commit.**

```bash
git add src/tidalist/core/fidelity.py tests/core/test_fidelity.py
git commit -F <msg>   # feat(core): audio-quality tiebreak in choose + QualityPreference  (+ trailer)
```

---

## Task 3: recording resolution applies the audio-quality tiebreak

**Files:** Modify `src/tidalist/realize/tidal.py`; Test `tests/realize/test_tidal.py`

**Interfaces:**
- Consumes: `QualityPreference`, `choose` (with `tiebreak`).
- Produces: `_track_candidate` populates `audio_quality`/`popularity`; `resolve` passes `tiebreak=lambda c: (_QUALITY_PREFERENCE.tiebreak(c), c.ref)` to `choose`, where `_QUALITY_PREFERENCE = QualityPreference()` is a module default.

- [ ] **Step 1: Write the failing test** in `tests/realize/test_tidal.py` (the `_track` helper builds a `Track`; extend it or build a Track directly with `audio_quality`):

```python
def test_resolve_prefers_hi_res_among_tied_hits():
    # Two hits, same song/artist/duration (tied identity); pick the hi-res one.
    lossy = _track("T-lossy", title="Glad", artists=("Traffic",), duration_s=200)
    hires = _track("T-hires", title="Glad", artists=("Traffic",), duration_s=200)
    lossy = replace(lossy, audio_quality="LOW")
    hires = replace(hires, audio_quality="HI_RES_LOSSLESS")
    cat = FakePlatform([lossy, hires])
    item, _ = TidalRealizer(cat).resolve(_rec(duration_s=200))
    assert item.ref == "T-hires"
```

(Use `from dataclasses import replace` at the top of the test module if not present, or extend the `_track` helper to accept `audio_quality`/`popularity` — either is fine.)

- [ ] **Step 2: Run to verify it fails** (without the quality tiebreak, the tie is broken by `ref` → "T-hires" vs "T-lossy" → "T-hires" wins alphabetically anyway? NO: "T-hires" < "T-lossy" lexicographically, so ref-tiebreak already picks "T-hires"). **To make the test discriminate, name the lossy candidate so it would win on `ref`:** rename `lossy` ref to `"T-aaa"` (sorts before "T-hires"). Then without the quality tiebreak `ref` picks "T-aaa" (lossy); with it, "T-hires" wins. Adjust the test:

```python
    lossy = _track("T-aaa", title="Glad", artists=("Traffic",), duration_s=200)
    hires = _track("T-hires", title="Glad", artists=("Traffic",), duration_s=200)
    lossy = replace(lossy, audio_quality="LOW")
    hires = replace(hires, audio_quality="HI_RES_LOSSLESS")
    cat = FakePlatform([lossy, hires])
    item, _ = TidalRealizer(cat).resolve(_rec(duration_s=200))
    assert item.ref == "T-hires"     # quality beats the lexicographically-smaller "T-aaa"
```

Run: `uv run pytest tests/realize/test_tidal.py -k prefers_hi_res -v`
Expected: FAIL — without the tiebreak, `ref` picks "T-aaa".

- [ ] **Step 3: Implement** in `realize/tidal.py`:
  - Import: `from ..core.fidelity import (..., QualityPreference)`.
  - Module default: `_QUALITY_PREFERENCE = QualityPreference()`.
  - In `_track_candidate`, populate the two fields:
    ```python
    def _track_candidate(track: Track) -> PlatformCandidate:
        return PlatformCandidate(
            ref=str(track.id), title=track.title, artists=track.artists,
            isrc=track.isrc, duration_s=track.duration_s,
            performance=_observe_performance(track.title),
            audio_quality=track.audio_quality, popularity=track.popularity,
        )
    ```
  - In `resolve`, pass the tiebreak:
    ```python
        chosen, comps = choose(recording, candidates, [IdentityFacet(), PerformanceFacet()],
                               tiebreak=lambda c: (_QUALITY_PREFERENCE.tiebreak(c), c.ref))
    ```

- [ ] **Step 4: Run the test + full offline suite.**

Run: `uv run pytest tests/realize/test_tidal.py -v` → PASS (the existing resolve tests still pass — they have a single clear winner, so the quality tiebreak doesn't change them)
Run: `uv run pytest -m "not integration" -q` → PASS

- [ ] **Step 5: Commit.**

```bash
git add src/tidalist/realize/tidal.py tests/realize/test_tidal.py
git commit -F <msg>   # feat(realize): recording resolution applies the audio-quality tiebreak  (+ trailer)
```

---

## Task 4: Slice-4 verification + landed docs

**Files:** Modify `TODO.md`

- [ ] **Step 1: Full offline suite.**

Run: `uv run pytest -m "not integration" -q`
Expected: PASS.

- [ ] **Step 2: Update `TODO.md`** — note slice 4 landed (audio-quality tiebreak); the uniform-realize arc's deferred items remain (source_kind / ReleaseClassFacet / per-track source attribution → rich-metadata backend; album-edition quality tiebreak; the cheap/local-LLM judge for title/identity matching). Commit:

```bash
git add TODO.md
git commit -F <msg>   # docs: uniform-realize slice 4 (audio-quality tiebreak) landed  (+ trailer)
```

*(The whole-branch review is run by the controller after this task.)*

---

## Remaining (roadmap — the uniform-realize arc's open tail)

- **`source_kind` (original > comp)** + **`ReleaseClassFacet`** + **per-track source-release attribution** — need a rich-metadata backend (torrent/local) or reliable structured class observation; title heuristics are too unreliable.
- **Album-edition quality tiebreak** — `PlatformAlbum` carrying `audio_quality`, so `resolve_album` editions tiebreak on quality too.
- **Cheap/local-LLM judge** for context-dependent title/identity matching — the fundamental limit of the deterministic string metrics.
