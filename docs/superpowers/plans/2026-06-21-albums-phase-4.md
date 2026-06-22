# Albums Phase 4 — Edition (criterion + preference + resolver)

> Execute task-by-task with TDD. Phase 4 of `2026-06-21-albums-and-identity.md`. Branch `albums-first`. Live-verify-first; MB shapes probed 2026-06-21.

**Goal:** Edition becomes first-class in three cooperating pieces: (1) an edition **criterion** that excludes compilations/live albums (clean MB signal); (2) a marker-based **EditionPreference/EditionPolicy** (default original; Steven Wilson / MoFi provenance markers) — backend-agnostic, lives with the golden intent; (3) a pure realize-time **edition resolver** that picks the closest *available* edition and reports a compromise. **Principle:** a backend's edition blindness (e.g. Tidal exposes no remixer/label) is a realization compromise — it never degrades the golden, and we still build the full machinery (other backends, and local files, honor it).

## Probed shapes

- MB release-group `secondary-type-list`: `['Compilation']` for a comp (Beatles "1962-1966"), `['Live']` for a live album, `None`/absent for a studio album. `primary-type` = "Album"/"Single"/etc. → the comp/live signal.

## Global Constraints

uv only; `uv run pytest -m "not integration" -q` green. Domain pure. Closed criterion tag-union (validated, never eval'd). Edition preference/markers are backend-agnostic; only the *resolver* knows about target editions.

---

### Task 1: edition criteria — exclude compilations and live albums

**Files:** `src/tidalist/core/album.py` (type fields), `src/tidalist/metadata/musicbrainz.py` (`album_from_release_group`), `src/tidalist/core/criteria.py` (type-aware `violation` + new criteria), `src/tidalist/core/golden.py` (Curator judges albums), `src/tidalist/core/spec.py` (album type + new criteria in the union). Tests across the matching test files.

**Interfaces:**
- `Album` gains `primary_type: str | None = None` and `secondary_types: tuple[str, ...] = ()`.
- `album_from_release_group(rg)` sets `primary_type = rg.get("primary-type")`, `secondary_types = tuple(rg.get("secondary-type-list") or ())`.
- `Criterion.violation(self, item: Album | Recording) -> str | None`. Existing `PerformedBy`/`Studio` guard `if not isinstance(item, Recording): return None` (so recording criteria are no-ops on albums — the north-star "except entire albums" falls out). New criteria judge an `Album`:
  - `NotCompilation` → `"compilation"` if `isinstance(item, Album) and "Compilation" in item.secondary_types` else None.
  - `NotLive` → `"live album"` if `isinstance(item, Album) and "Live" in item.secondary_types` else None.
- `Brief.judge(item: Album | Recording)` unchanged in body (it already loops `c.violation(item)`), just the type widens.
- The golden `Curator` album path now **judges** the chosen album via `brief.judge(album)` (replacing Phase 3's unconditional `Verdict.ok()`); a miss still yields the rejected stub.
- `spec.py`: `_criterion_to_dict`/`_from_dict` gain `{"type":"not_compilation"}` / `{"type":"not_live"}`; the album golden-entry dict gains `"primary_type"` and `"secondary_types"`, and `_golden_entry_from_dict` reconstructs them.

- [ ] **Step 1 — failing tests:** `Album` carries `primary_type`/`secondary_types`; `album_from_release_group` maps `secondary-type-list`; `NotCompilation.violation(Album(..., secondary_types=("Compilation",)))` returns a reason while `NotCompilation.violation(<a Recording>)` is None; `PerformedBy.violation(<an Album>)` is None; a Curator album candidate under a `NotCompilation` brief is **rejected** when the album is a compilation and **admitted** when not; the album golden entry round-trips `primary_type`/`secondary_types`.
- [ ] **Step 2 — watch fail; Step 3 — implement** per the interfaces; **Step 4 — green** (full offline suite; existing Phase 3 album tests still pass — recording criteria are no-ops on albums).
- [ ] **Step 5 — commit** (verbatim): `feat(core): edition criteria — exclude compilations and live albums`

---

### Task 2: `EditionPreference` + `EditionPolicy`

**Files:** Create `src/tidalist/core/edition.py`; Test: `tests/core/test_edition.py`.

**Interfaces:** backend-agnostic value objects (no I/O, no target knowledge):
- `EditionPreference(markers: tuple[str, ...] = (), prefer_original: bool = True)` — `markers` is an ordered provenance preference (e.g. `("steven wilson", "mobile fidelity")`), lowercased; `prefer_original` favors the canonical/earliest edition when no marker matches.
- `EditionPolicy` — the standing default. `EditionPolicy.default()` returns `EditionPreference(markers=("steven wilson", "mobile fidelity"), prefer_original=True)` (the baked-in Steven Wilson-then-MoFi default). A per-entry `EditionPreference` overrides the policy when present.

- [ ] **Step 1 — failing tests:** `EditionPreference` defaults (`markers == ()`, `prefer_original is True`); `EditionPolicy.default().markers[0] == "steven wilson"`; markers are stored lowercased.
- [ ] **Step 2 — watch fail; Step 3 — implement** the frozen VOs; **Step 4 — green.**
- [ ] **Step 5 — commit** (verbatim): `feat(core): EditionPreference + EditionPolicy (default original; Steven Wilson provenance)`

---

### Task 3: edition resolver — closest available edition + compromise report

**Files:** Modify `src/tidalist/core/realize.py` (add the resolver + `EditionOption`); Test: `tests/core/test_realize.py`.

**Interfaces:** a pure function, target-agnostic (the realizer feeds it the target's editions in Phase 5):
- `EditionOption(ref: str, title: str, year: int | None = None)` — one available edition on a platform (`ref` is the platform handle; `title` is what the platform exposes, e.g. a Tidal album title).
- `choose_edition(options: list[EditionOption], preference: EditionPreference) -> tuple[EditionOption | None, str | None]` — returns `(chosen, compromise)`:
  - if a preference marker (in order) appears (casefold substring) in some option's title → choose the first such option, `compromise = None`.
  - else if `prefer_original` → choose the option that looks most original: lowest year, and among ties prefer titles WITHOUT `"reissue"`/`"remaster"`/`"deluxe"`; `compromise = f"preferred edition ({markers[0]}) unavailable"` when `markers` was non-empty, else None.
  - empty `options` → `(None, None)`.

- [ ] **Step 1 — failing tests:** marker match wins (a "… (Steven Wilson Mix)" option chosen over an original when `markers=("steven wilson",)`, no compromise); no-marker falls back to original (earliest, non-reissue) with a compromise string naming the unavailable preferred marker; empty → `(None, None)`.
- [ ] **Step 2 — watch fail; Step 3 — implement; Step 4 — green.**
- [ ] **Step 5 — commit** (verbatim): `feat(realize): edition resolver — closest available edition + compromise report`

## Phase-4 done check
- Offline green. Edition criterion excludes comps/live (album-level, type-aware criteria; recording criteria still no-op on albums). `EditionPreference`/`EditionPolicy` exist with the Steven Wilson default. `choose_edition` picks by marker then originality and reports compromises — ready for Phase 5 to feed Tidal's editions in. The golden carries edition intent; no realization limitation bled back.

## Future: rich-metadata realizers & the region axis (out of scope — captured)
Tidal's edition-blindness is one extreme; the other is a **private-tracker / torrent realizer** (cf. the user's Redacted classical-tagger work) carrying the *richest* edition metadata — encoding/media (FLAC; CD/Vinyl/SACD/WEB), label/catalog, remaster/remix tags, **and multiple foreign/regional releases** of the same album (Japanese pressings, etc.). This validates the marker-based design: such a backend honors provenance markers (Steven Wilson, MoFi) fully, and the **region dimension is just more markers** (`"japan"`, `"uk"`) — `EditionPreference.markers` absorbs it with no model change. The hard parts (which regional edition is canonical, bonus-track divergence) are a realize-stage concern for *that* realizer when built; the golden stays region-agnostic.
