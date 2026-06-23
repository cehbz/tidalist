# Uniform Realize — Slice 3 (Track-Level Album Fallback) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a golden album's release-group is absent on the platform, stop gapping it — **assemble its canonical tracklist track-by-track** from individual platform tracks (compilations, live albums, other releases), reporting a typed `album-source` compromise (with missing positions) instead of a gap. Captain Beefheart's *Trout Mask Replica* (absent as an album, many tracks present via compilations) is the live fixture.

**Architecture:** Reuses slice-2's facet-native recording `resolve`. The change is almost entirely in the Tidal adapter: `TidalRealizer.resolve_album`'s "no edition found" branch (today a gap) now calls a per-track assembler that resolves each `TrackRef` via `self.resolve`. No facet-framework or core value-object changes.

**Tech Stack:** Python 3.12 (uv), stdlib-only core, `pytest`. Run via `uv run`.

## Global Constraints

- uv only; `uv run pytest -m "not integration"` (offline) / `uv run pytest` (with live, needs creds). `pythonpath=["src","."]`.
- Domain core stays pure; this slice touches only the adapter (`realize/tidal.py`) and tests.
- TDD red→green; RED is a failing assertion (not an import error).
- **Baseline at slice-3 start: 318 offline passing + 6 deselected** (branch `uniform-realize-slice-2` HEAD `84a9caa`).
- The edition-selection path (a release-group that IS on the platform) is unchanged — Mr. Fantasy still resolves to the 10-track original. Only the previously-gapping branch changes.
- Existing no-tracklist gap tests must stay green (assembly requires a tracklist; a golden album with no tracklist still gaps).
- Commit messages are pre-approved (shown per task). Each ends with:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

## Design notes (decisions approved 2026-06-23)

- **Trigger = `_search_survivors` empty** (release-group genuinely absent). A found-but-incomplete edition is NOT re-assembled — edition selection already picks the best available edition.
- **`ReleaseClassFacet` dropped from this slice** — no consumer yet (assembly candidates are bare tracks with no observed source-album class; editions of one release-group share their class). Its home is alongside source-release attribution / a rich-metadata backend.
- **Source attribution simplified:** the `album-source` compromise reports **counts + missing positions** ("assembled 22/28 tracks … missing positions 4, 9"), not the specific N releases each track came from (which needs per-track source-album lookups deferred to the rich-backend work).
- Per-track compromises from the inner `resolve` (e.g. a performance substitution on one track) are **not** propagated in this slice; the headline is the album-level `album-source` compromise. (The canonical tracklist carries ISRCs, so exact identity usually wins per track anyway.)
- The assembler issues one `search_tracks` per missing-ISRC track (N calls for an N-track album); acceptable (tidalapi self-throttles). Batching is a later optimization.

## File structure

- **Modify `src/tidalist/realize/tidal.py`** — `resolve_album`'s `if not survivors` branch calls a new `_assemble_from_tracks`; add `_assemble_from_tracks`, `_recording_from_trackref`, `_album_source_compromise`; import `TrackRef`.
- **Modify `tests/realize/test_tidal.py`** — offline assembly tests (partial assemble; gap when zero found; gap when no tracklist).
- **Create `tests/realize/test_track_fallback_live.py`** — the live *Trout Mask Replica* integration test.

---

## Task 1: Assemble an absent album from individual platform tracks

**Files:** Modify `src/tidalist/realize/tidal.py`; Test `tests/realize/test_tidal.py`

**Interfaces:**
- Consumes: `self.resolve` (slice-2 recording resolution), `TrackRef`/`Album` (core.album), `Recording` (core.recording), `Compromise` (core.fidelity, already imported), `PlatformItem`/`MatchQuality`.
- Produces: `TidalRealizer.resolve_album` now assembles instead of gapping when no edition is found. New module helpers `_recording_from_trackref(album, tr) -> Recording` and `_album_source_compromise(album, found, total, missing) -> Compromise`.

- [ ] **Step 1: Write the failing tests** (append to `tests/realize/test_tidal.py`; the `_track_ref`, `_album_track`, `_album`, `FakePlatform`, `EditionPolicy` helpers already exist there):

```python
def test_resolve_album_assembles_from_tracks_when_album_absent():
    golden = Album(artist="Captain Beefheart", title="Trout Mask Replica",
                   tracklist=(_track_ref(1, "Frownland"),
                              _track_ref(2, "The Dust Blows Forward"),
                              _track_ref(3, "Dachau Blues")))
    # No album matches the search; tracks for positions 1 and 3 exist individually.
    t1 = _album_track("T1", "Frownland", artists=("Captain Beefheart",))
    t3 = _album_track("T3", "Dachau Blues", artists=("Captain Beefheart",))
    cat = FakePlatform([t1, t3], albums=[])      # search_albums empty -> assembly path
    items, comps = TidalRealizer(cat).resolve_album(golden, EditionPolicy.default())
    assert [i.ref for i in items] == ["T1", "T3"]
    assert len(comps) == 1 and comps[0].facet == "album-source"
    assert "2/3" in comps[0].note
    assert "2" in comps[0].note                  # missing position 2 reported


def test_resolve_album_gaps_when_no_tracks_assemble():
    golden = Album(artist="X", title="Absent Album", tracklist=(_track_ref(1, "Nope"),))
    cat = FakePlatform([], albums=[])
    items, comps = TidalRealizer(cat).resolve_album(golden, EditionPolicy.default())
    assert items == [] and comps == ()


def test_resolve_album_no_tracklist_gaps():
    golden = Album(artist="X", title="Absent Album")   # no tracklist -> cannot assemble
    cat = FakePlatform([], albums=[])
    items, comps = TidalRealizer(cat).resolve_album(golden, EditionPolicy.default())
    assert items == [] and comps == ()
```

- [ ] **Step 2: Run to verify the assembly test fails** (the gap tests already pass — current behavior gaps; the new assembly test fails because today's `not survivors` branch returns `[], ()`).

Run: `uv run pytest tests/realize/test_tidal.py -k "assembles or no_tracks_assemble or no_tracklist" -v`
Expected: `test_resolve_album_assembles_from_tracks_when_album_absent` FAILS (returns `[], ()`); the two gap tests PASS already.

- [ ] **Step 3: Implement.** In `src/tidalist/realize/tidal.py`:
  - Add `TrackRef` to the album import: `from ..core.album import Album, TrackRef`.
  - Replace the `if not survivors: return [], ()` line in `resolve_album` with:
    ```python
        if not survivors:
            return self._assemble_from_tracks(album)
    ```
  - Add the assembler method to `TidalRealizer`:
    ```python
        def _assemble_from_tracks(self, album: Album) -> tuple[list[PlatformItem], tuple[Compromise, ...]]:
            """When no edition of the release-group is on the platform, assemble the
            canonical tracklist track-by-track from individual catalog tracks."""
            if not album.tracklist:
                return [], ()
            items: list[PlatformItem] = []
            missing: list[int] = []
            for tr in album.tracklist:
                item, _ = self.resolve(_recording_from_trackref(album, tr))
                if item is not None:
                    items.append(item)
                else:
                    missing.append(tr.position)
            if not items:
                return [], ()
            comp = _album_source_compromise(album, len(items), len(album.tracklist), missing)
            return items, (comp,)
    ```
  - Add the module-level helpers (near `_item`/`_query`):
    ```python
    def _recording_from_trackref(album: Album, tr: TrackRef) -> Recording:
        return Recording(artist=album.artist, title=tr.title, isrc=tr.isrc,
                         mbid=tr.mbid, duration_s=tr.duration_s)


    def _album_source_compromise(album: Album, found: int, total: int,
                                 missing: list[int]) -> Compromise:
        note = (f"album '{album.title}' unavailable; assembled {found}/{total} tracks "
                f"from individual catalog tracks")
        if missing:
            note += f" (missing positions: {', '.join(str(p) for p in missing)})"
        return Compromise("album-source", album.title,
                          f"assembled {found}/{total} tracks", note)
    ```

- [ ] **Step 4: Run the new tests, then the full offline suite.**

Run: `uv run pytest tests/realize/test_tidal.py -v` → PASS (including the existing `test_resolve_album_returns_empty_when_nothing_matches` / `test_resolve_album_drops_wrong_artist`, which gap correctly because `_domain_album()` has no tracklist).
Run: `uv run pytest -m "not integration" -q` → PASS (321: 318 + 3 new).

- [ ] **Step 5: Commit.**

```bash
git add src/tidalist/realize/tidal.py tests/realize/test_tidal.py
git commit -F <msg>   # feat(realize): assemble an absent album from individual platform tracks  (+ trailer)
```

---

## Task 2: Live Trout Mask Replica assembly (integration)

**Files:** Create `tests/realize/test_track_fallback_live.py` (`@pytest.mark.integration`)

The deterministic assembly is proven offline in Task 1. This live test confirms the real case end-to-end: the album is absent on Tidal, but its canonical tracklist (from MusicBrainz) assembles partially from compilation tracks, yielding an `album-source` compromise rather than a gap.

- [ ] **Step 1: Write the integration test.** Mirror the live-setup pattern in `tests/realize/test_edition_distance_live.py` and `tests/metadata/test_albums_live.py` (build a real `MusicBrainzMetadata` provider and a real `TidalPlatform`/`TidalRealizer` from `AppConfig`). Get the golden album (with its canonical tracklist) for Captain Beefheart's *Trout Mask Replica* via `MusicBrainzMetadata.albums_for`, then assemble:

```python
import pytest


@pytest.mark.integration
def test_trout_mask_replica_assembles_from_compilations(...):
    # provider = MusicBrainzMetadata(...); realizer = TidalRealizer(TidalPlatform(authenticate()))
    candidate = Candidate(artist="Captain Beefheart", title="Trout Mask Replica", kind=Kind.ALBUM)
    album = next(a for a in provider.albums_for(candidate) if a.tracklist)
    items, comps = realizer.resolve_album(album, EditionPolicy.default())
    assert items                                  # not a gap — partial assembly succeeded
    assert any(c.facet == "album-source" for c in comps)
```

- [ ] **Step 2: Run it live.**

Run: `uv run pytest tests/realize/test_track_fallback_live.py -v`
Expected: PASS (partial assembly + `album-source` compromise). If Tidal/MB return nothing usable for this artist spelling, try the alternate artist name ("Captain Beefheart & His Magic Band") and document the working one. If no stable fixture emerges, report DONE_WITH_CONCERNS (deferred) and do not commit — do not fake a pass.

- [ ] **Step 3: Commit (only if the live test is real and green).**

```bash
git add tests/realize/test_track_fallback_live.py
git commit -F <msg>   # test(realize): live — Trout Mask Replica assembles from compilations (partial)  (+ trailer)
```

---

## Task 3: Slice-3 verification + landed docs

**Files:** Modify `TODO.md`

- [ ] **Step 1: Full offline suite.**

Run: `uv run pytest -m "not integration" -q`
Expected: PASS (321).

- [ ] **Step 2: Update `TODO.md`** — note slice 3 landed (track-level album fallback); slice 4 remains. Commit:

```bash
git add TODO.md
git commit -F <msg>   # docs: uniform-realize slice 3 (track-level album fallback) landed  (+ trailer)
```

*(The whole-branch review is run by the controller after this task.)*

---

## Subsequent slice (roadmap)

- **Slice 4 — Quality-preference policy depth:** flesh `AudioFacet` into a specifiable policy (original-source > comp, hi-res > lossy, popularity), superseding `choose`'s `ref` tiebreak. Also the natural home for the deferred `ReleaseClassFacet` and per-track source-release attribution once candidates carry observed class/source. (And, longer-term, a cheap/local-LLM judge for context-dependent title/identity matching — the fundamental limit of the deterministic string metrics.)
