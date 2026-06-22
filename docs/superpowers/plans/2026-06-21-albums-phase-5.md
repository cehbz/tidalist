# Albums Phase 5 — Album realization (Tidal)

> Execute task-by-task with TDD. Phase 5 of `2026-06-21-albums-and-identity.md`. Branch `albums-first`. Live-verify-first; Tidal shapes probed 2026-06-21.

**Goal:** Realize a golden `Album` onto Tidal: find the album (identity-filtered), pick the edition via `choose_edition`, expand to its tracks in order, and report album gaps + edition compromises. Recording realization is unchanged.

## Probed Tidal shapes

- `session.search(query, models=[tidalapi.album.Album], limit=N)` → `{"albums": [album, …]}`; each album has `.id`, `.name`, `.year`, `.artists` (list with `.name`), `.num_tracks`. Search is **fuzzy** ("King Crimson In the Court…" also returns Pink Floyd, Fleshgod Apocalypse) → must identity-filter by artist + title.
- Editions appear as **separate albums** by name + track count: "John Barleycorn Must Die" (8) vs "…Deluxe Edition" (16). Feed each survivor's `name`/`year` into `choose_edition`.
- `album.tracks()` → ordered Track objects (map with the existing `track_from_tidal`); tracks carry ISRC.

## Global Constraints

uv only; `uv run pytest -m "not integration" -q` green. Domain pure; `cli.py` presentation only. Adapter unit-tested against `FakeCatalog`; live behavior in a `@pytest.mark.integration` test (Task 3) that also creates ONE disposable real playlist (the controller confirms its name with the user before running it).

---

### Task 1: TidalRealizer resolves an album to its tracks in order

**Files:** `src/tidalist/core/catalog.py` (a `CatalogAlbum` VO), `src/tidalist/core/ports.py` (Catalog gains album methods), `src/tidalist/tidal/catalog.py` (TidalCatalog impl), `src/tidalist/realize/tidal.py` (`resolve_album`), `tests/fakes.py` (FakeCatalog album methods). Tests: `tests/realize/test_tidal.py`, `tests/tidal/test_catalog.py`.

**Interfaces:**
- `CatalogAlbum(id: TrackId, title: str, artists: tuple[str, ...], year: int | None = None, num_tracks: int | None = None)` in `catalog.py` (a platform album descriptor; reuse `TrackId` for `id`).
- `Catalog` port gains `search_albums(self, query: str, limit: int = 25) -> list[CatalogAlbum]` and `album_tracks(self, album_id: TrackId) -> list[Track]` (ordered).
- `TidalCatalog.search_albums` → `session.search(query, models=[tidalapi.album.Album], limit=limit)["albums"]` mapped to `CatalogAlbum` (id=str, title=`.name`, artists=tuple of artist names, year=`.year`, num_tracks=`.num_tracks`). `TidalCatalog.album_tracks(id)` → `session.album(id).tracks()` mapped via `track_from_tidal`.
- `TidalRealizer.resolve_album(self, album: Album, preference: EditionPreference) -> tuple[list[PlatformItem], str | None]`: `search_albums(f"{album.artist} {album.title}")`; keep candidates whose artist matches `album.artist` (casefold substring either way) AND whose title matches `album.title` (casefold substring); build an `EditionOption(ref=str(c.id), title=c.title, year=c.year)` per survivor; `choose_edition(options, preference)`; if a chosen option → `album_tracks(chosen.ref)` mapped to `PlatformItem` (quality `MatchQuality.STRONG`), return `(items, compromise)`; if none → `([], None)`.
- `FakeCatalog` gains `search_albums` (over a seeded `albums: list[CatalogAlbum]`, filtered by query words like `search_tracks`) and `album_tracks` (over a seeded `{album_id: [Track,…]}` map).

- [ ] **Step 1 — failing tests:** `resolve_album` drops a wrong-artist album (the fuzzy-noise case), picks the original edition over a "Deluxe Edition" when preference is `EditionPolicy.default()` (no SW marker present → original fallback), returns its tracks as `PlatformItem`s in order, and `([], None)` when no album matches. `TidalCatalog` mapping is covered by a fake tidalapi session (mirror the existing `test_catalog.py` style).
- [ ] **Step 2 — watch fail; Step 3 — implement; Step 4 — green** (offline suite).
- [ ] **Step 5 — commit** (verbatim): `feat(realize): TidalRealizer resolves an album to its tracks in order`

---

### Task 2: Realization reports album gaps and edition compromises

**Files:** `src/tidalist/core/realize.py` (generalize `RealizedEntry`; `realize`/`publish`), `src/tidalist/cli.py` (`format_realization`). Tests: `tests/core/test_realize.py`, `tests/test_cli.py`.

**Interfaces:**
- `RealizedEntry(golden: GoldenEntry, items: tuple[PlatformItem, ...] = (), compromise: str | None = None)` — `items` is empty for a gap, one for a resolved recording, many for a resolved album. `is_gap` → `not self.items`. (Update the recording path: a resolved recording → `items=(item,)`.)
- `realize(golden, realizer, preference: EditionPreference = EditionPolicy.default())`: per admitted entry — `Recording` item → `realizer.resolve(item)`; `items=(pi,)` if found else `()`. `Album` item → `items, compromise = realizer.resolve_album(item, preference)`. Build `RealizedEntry` accordingly.
- `Realization.gaps()` → entries with no items; `resolved()` → entries with items. Add `Realization.compromises() -> tuple[tuple[GoldenEntry, str], ...]` (entries whose `compromise` is not None).
- `publish` flattens `e.items for e in realization.resolved()` into the emit list.
- `cli.format_realization`: a resolved album line shows its track count; gap and compromise lines noted (e.g. `… [edition compromise: <note>]`).

- [ ] **Step 1 — failing tests:** an admitted `Album` entry whose realizer returns tracks → a resolved entry holding those items; an album entry with a compromise note surfaces in `compromises()`; `publish` emits all album tracks; a recording entry still works (one item); gaps still detected. Update existing realize/cli tests for `items`.
- [ ] **Step 2 — watch fail; Step 3 — implement; Step 4 — green** (offline suite).
- [ ] **Step 5 — commit** (verbatim): `feat(core): Realization reports album gaps and edition compromises`

---

### Task 3: live Tidal album-realization integration test

**Files:** Test: `tests/realize/test_tidal_live.py` (new), `@pytest.mark.integration`, skipped without a Tidal session.

- [ ] **Step 1 — write tests** (resolve only; no write): build a `TidalRealizer(TidalCatalog(authenticate(session_file)))`; `resolve_album(Album("Traffic","John Barleycorn Must Die"), EditionPolicy.default())` returns ~8 `PlatformItem`s (the original, not the 16-track Deluxe) whose titles include "Glad"; a wrong album yields `([], …)`.
- [ ] **Step 2 — controller runs it live** (read-only resolve).
- [ ] **Step 3 — live publish smoke (CONTROLLER, gated):** the controller, AFTER confirming the playlist name with the user, runs a one-off that curates→realizes→publishes a tiny album golden to a real disposable Tidal playlist and prints its reference. Not an automated test (it writes); done once, by hand, with user consent.
- [ ] **Step 4 — confirm offline suite deselects the integration test. Commit** (verbatim): `test(realize): live Tidal album-realization integration test`

## Phase-5 done check
- Offline green; live resolve test passes (Traffic JBMD → original edition's 8 tracks, Deluxe rejected, fuzzy noise filtered). One real playlist created by hand with the user's OK. Recording realization unchanged. Album entries realize to ordered tracks with gaps + edition compromises reported.
