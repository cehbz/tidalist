# Albums Phase 6 — Intent schema, front-ends, the Winwood north-star

> Execute task-by-task with TDD. Final phase of `2026-06-21-albums-and-identity.md`. Branch `albums-first`. Pure local (no live network in the committed tests).

**Goal:** The intent JSON carries everything the agent decides per candidate (kind, per-candidate criteria, edition preference, identity hint); the Scaruffi front-end emits album-kind classical entries; the **Steve Winwood** prompt lands as the end-to-end acceptance fixture; docs refreshed. Then the branch is ready for the pre-merge review.

## Global Constraints

uv only; `uv run pytest -m "not integration" -q` green. Domain pure. Closed criterion union. **Avoid import cycles:** `recording.py` must not import `criteria`/`edition`/`album` at runtime — use `from __future__ import annotations` + `TYPE_CHECKING` for any such field annotations (the field *values* are plain tuples/objects; no runtime class needed to store them).

---

### Task 1: intent schema gains kind, per-candidate criteria, edition prefs, identity hints

**Files:** `src/tidalist/core/recording.py` (Candidate fields), `src/tidalist/core/spec.py` (candidate (de)serialization + the per-candidate union), `src/tidalist/core/golden.py` (Curator combines brief + candidate criteria; carries edition pref), `src/tidalist/metadata/musicbrainz.py` (use the identity hint), `src/tidalist/nl/intent.py` (contract doc). Tests across the matching test files.

**Interfaces:**
- `Candidate` gains (all defaulted, so existing call sites are unaffected; use `TYPE_CHECKING` annotations to avoid cycles):
  - `criteria: tuple["Criterion", ...] = ()` — per-candidate criteria, combined with the brief's at judging.
  - `edition: "EditionPreference | None" = None` — a per-candidate edition override (else the realize-time policy default applies).
  - `artist_mbid: MBID | None = None` — identity hint; when set, the MB provider uses it directly instead of resolving the artist by search.
- `spec.py`: `_candidate_to_dict`/`_from_dict` serialize `criteria` (list via the existing `_criterion_to_dict` union), `edition` (`{"markers": [...], "prefer_original": bool}` or omitted when None), and `artist_mbid`. Add `_edition_to_dict`/`_from_dict` helpers.
- `golden.py` Curator: when judging an entry, use `brief.criteria + candidate.criteria` (combined) — build a transient `Brief(brief.name, brief.criteria + candidate.criteria)` or judge against both. Carry `candidate.edition` onto the resulting `GoldenEntry` (see below).
- `GoldenEntry` gains `edition: "EditionPreference | None" = None` (the per-entry realize hint); `spec.py` golden-entry (de)serialization round-trips it; `realize()` uses `entry.edition or preference` when resolving an album.
- `musicbrainz.py`: `recordings_for`/`albums_for` use `candidate.artist_mbid or self._artist_mbid(candidate.artist)`.
- `nl/intent.py`: update the contract docstring to show `kind`, per-candidate `criteria`, `edition`, `artist_mbid`.

- [ ] **Step 1 — failing tests:** a `Candidate` with per-candidate `criteria` is judged by them in the Curator (a track candidate carrying `PerformedBy(X)` is rejected as a cover even with an empty brief); `artist_mbid` hint bypasses artist resolution in the MB provider (no `search_artists` call when set); intent round-trips `kind`/`criteria`/`edition`/`artist_mbid`; `GoldenEntry.edition` round-trips and `realize()` uses it.
- [ ] **Step 2 — watch fail; Step 3 — implement; Step 4 — green** (full offline suite; existing tests unaffected by the new defaulted fields).
- [ ] **Step 5 — commit** (verbatim): `feat(nl): intent schema gains kind, per-candidate criteria, edition prefs, identity hints`

---

### Task 2: Scaruffi front-end — album kind + edition context

**Files:** `src/tidalist/scaruffi/parse.py`; Test: `tests/scaruffi/test_parse.py`.

**Interfaces:** Scaruffi recommendations are whole works → `kind=Kind.ALBUM` (already set). Add edition context: the recommended **year** flows to the candidate (`year=` already), and the recommended performer + alternates stay in the provenance note. If a recommendation names a specific edition/label in the note, leave it as provenance text (no structured edition pref — Scaruffi's text is a hint, not a marker list). This task confirms album-kind + threads the year as the original-edition hint and adds a test that a Scaruffi candidate is `kind=ALBUM` with its year.

- [ ] **Step 1 — failing test:** a parsed Scaruffi candidate is `kind=Kind.ALBUM` and carries the recommended `year`; its provenance note carries the performer (already). (If parse.py already satisfies this, the test is the deliverable + any small thread-through.)
- [ ] **Step 2 — watch fail/confirm; Step 3 — implement; Step 4 — green.**
- [ ] **Step 5 — commit** (verbatim): `feat(scaruffi): classical works carry album kind + edition context`

---

### Task 3: Steve Winwood north-star end-to-end acceptance fixture

**Files:** Create `tests/fixtures/winwood_intent.json`; Test: `tests/test_winwood_acceptance.py`.

**Interfaces:** the fixture encodes the user's verbatim prompt as a real intent — a **mix** of album entries (`kind:"album"`: Traffic *Mr. Fantasy* / *John Barleycorn Must Die* / *Low Spark…*, Blind Faith, a Spencer Davis album) and track entries (`kind:"track"` with per-candidate `criteria:[{"type":"performed_by","artist":"Steve Winwood"}]`: *Gimme Some Lovin'*, *Higher Love*, *Valerie*), brief `criteria:[{"type":"not_compilation"}]`, with provenance notes. The acceptance test runs the **offline** pipeline against fakes anchored to the probed live shapes: `parse_intent` → `Curator.curate` (a `FakeMetadataProvider` seeded so album candidates resolve to `Album`s and track candidates to identity-matched `Recording`s) → assert the golden has both album and track admitted entries, covers excluded, mixed kinds preserved; then `realize` against a `FakeRealizer`/`FakeCatalog` → assert album entries expand to tracks and the playlist publishes. This is the executable proof of the whole feature.

- [ ] **Step 1 — write the fixture + the failing acceptance test** (assert the mix curates + realizes as above).
- [ ] **Step 2 — watch fail; Step 3 — make it pass** (it should, if Phases 1-5 + Task 1 are correct — fix anything it surfaces); **Step 4 — green.**
- [ ] **Step 5 — commit** (verbatim): `test: Steve Winwood north-star end-to-end acceptance fixture`

---

### Task 4: refresh README + plan status

**Files:** `README.md`, `docs/superpowers/plans/2026-06-21-albums-and-identity.md` (status), `TODO.md` if needed.

**Interfaces:** README documents album support (`kind`, the intent schema additions, edition preference, the comp/live criterion); the architecture spec's status notes Phases 1-6 done; TODO trimmed.

- [ ] **Step 1 — update README** (album-aware intent JSON example: a mixed album/track playlist; note edition preference is best-effort per backend); **update the spec status**; trim `TODO.md`.
- [ ] **Step 2 — `uv run pytest -m "not integration" -q` still green** (docs only). **Commit** (verbatim): `docs: refresh README + plan status for albums-first`

## Phase-6 done check
- Offline green; the Winwood acceptance test passes (mixed album/track playlist curates + realizes). Intent schema carries kind/criteria/edition/identity per candidate; Scaruffi emits album kind. Docs current. **Branch ready for the pre-merge whole-branch review.**
