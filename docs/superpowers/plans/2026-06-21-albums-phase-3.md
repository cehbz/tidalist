# Albums Phase 3 — Album discovery

> Execute task-by-task with TDD. Phase 3 of `2026-06-21-albums-and-identity.md`. Branch `albums-first`. Live-verify-first; shapes probed against real MusicBrainz + Discogs 2026-06-21.

**Goal:** `MetadataProvider.albums_for(candidate) -> list[Album]`, identity-matched (same artist-MBID filter as recordings). The golden Curator routes `kind == ALBUM` candidates to `albums_for` and emits `Album` golden entries; `kind == TRACK` keeps today's `recordings_for` path. MusicBrainz release-groups are the album-identity source; Discogs masters are a coarse secondary source (the edition anchor; Phase 4 uses its attributes).

## Probed shapes (anchor fakes to these)

- `mb.search_release_groups(artist=A, releasegroup=T, limit=N)` → `{"release-group-list": [{"id", "title", "first-release-date" (e.g. "1970-07"), "primary-type" (e.g. "Album"), "artist-credit": [{"artist": {"id","name"}}, …], "artist-credit-phrase", "ext:score"}, …]}`. Top hit for "Traffic"/"John Barleycorn Must Die" is the album credited to Traffic `9fadfba9…`; other hits are different artists. Filter by the resolved artist MBID (reuse the credit-match logic).
- Discogs `client.search(query, type="master")` → lazily-paginated master objects with `.id`, `.title` ("Artist - Album"), `.year` (often `None` on the search result). Bound with `itertools.islice` (same pagination trap as recordings).

## Global Constraints

uv only; `uv run pytest -m "not integration" -q` green. Domain pure. Adapters unit-tested against fakes anchored to the shapes above; live behavior in a `@pytest.mark.integration` test (Task 4), skipped without creds. `Album` is `Album(artist, title, mbid=None, first_released=None)` (`from .album import Album`).

---

### Task 1: `MetadataProvider.albums_for` port

**Files:** Modify `src/tidalist/core/ports.py`; Modify `tests/fakes.py` (`FakeMetadataProvider`); Test: `tests/test_fakes.py` or `tests/core/` as fits.

**Interfaces:** the `MetadataProvider` Protocol gains `def albums_for(self, candidate: Candidate) -> list[Album]: ...` (alongside `recordings_for`). `FakeMetadataProvider` gains an `albums` map (keyed by candidate title, case-insensitive) and `albums_for` returning the matching list (default `[]`), mirroring its `recordings_for`.

- [ ] **Step 1 — failing test:** a `FakeMetadataProvider` seeded with an album for a title returns it from `albums_for`, and `[]` for an unknown title. (Write the test; watch it fail — `albums_for` undefined.)
- [ ] **Step 2 — implement:** add `albums_for` to the `MetadataProvider` Protocol in `ports.py` (import `Album`); extend `FakeMetadataProvider.__init__(self, recordings=None, albums=None)` and add `albums_for` mirroring `recordings_for`. Keep existing `FakeMetadataProvider(recordings)` call sites working (recordings as first positional).
- [ ] **Step 3 — green** (full offline suite). **Commit** (verbatim): `feat(core): MetadataProvider.albums_for port`

---

### Task 2: `albums_for` in MusicBrainz (release-groups) and Discogs (masters)

**Files:** Modify `src/tidalist/metadata/musicbrainz.py`, `src/tidalist/metadata/discogs.py`; Test: `tests/metadata/test_musicbrainz.py`, `tests/metadata/test_discogs.py`.

**Interfaces:**
- `MusicBrainzMetadata.albums_for(candidate) -> list[Album]`: resolve artist MBID (reuse `_artist_mbid`); `self._mb.search_release_groups(artist=candidate.artist, releasegroup=candidate.title, limit=self._limit)`; keep hits credited to the artist MBID (reuse the credit-match helper — generalize `_credited_to` to accept the `artist-credit` list, or call on the rg dict); map each to `Album`. Map: `Album(artist = rg.get("artist-credit-phrase") or <first credit name>, title = rg["title"], mbid = MBID(rg["id"]), first_released = <int year from rg.get("first-release-date")[:4] if digits>)`. Add a `album_from_release_group(rg: dict) -> Album` mapper (mirrors `recording_from_musicbrainz`). The `_FakeMB` double gains `search_release_groups(self, artist="", releasegroup="", limit=None, **kw)` returning `{"release-group-list": self._release_groups}`.
- `DiscogsMetadata.albums_for(candidate) -> list[Album]`: `self._limiter.wait()`; `itertools.islice(self._client.search(f"{candidate.artist} {candidate.title}", type="master"), self._limit)`; map each master to `Album(artist=candidate.artist, title=candidate.title, mbid=None, first_released=_year(master))` (reuse the existing `_year`). Add `album_from_discogs(master, candidate) -> Album`.

- [ ] **Step 1 — failing tests:**
  - MB: `album_from_release_group({...})` maps id→mbid, title, first-release-date→year, credit-phrase→artist; and `albums_for` drops release-groups not credited to the resolved artist (a fake with a Traffic rg + a different-artist rg → only Traffic's kept).
  - Discogs: `albums_for` maps masters to Albums with `mbid is None` and the candidate's artist/title; islice-bounded (lazy fake, like the recordings pagination test).
- [ ] **Step 2 — watch fail; Step 3 — implement** per the interfaces above.
- [ ] **Step 4 — green** (full offline suite). **Commit** (verbatim): `feat(metadata): albums_for via MusicBrainz release-groups + Discogs masters`

---

### Task 3: Curator discriminates album candidates

**Files:** Modify `src/tidalist/core/golden.py`; Test: `tests/core/test_golden.py`.

**Interfaces:** `Curator._entry` branches on `candidate.kind`:
- `Kind.TRACK` (default): today's behavior — `recordings_for`, judge via brief criteria, rank, choose; misses → rejected recording entry.
- `Kind.ALBUM`: `albums_for(candidate)`; if empty → a rejected `Album(candidate.artist, candidate.title)` entry (verdict `rejected("no album found")`); else pick the first album (identity-filtered, MB-score-ordered) and emit a `GoldenEntry(album, provenance, Verdict.ok())`. **Recording-level brief criteria do NOT gate album entries** (per the north-star "except entire albums").

- [ ] **Step 1 — failing tests** (use `FakeMetadataProvider` with an `albums` map):
  - an `ALBUM` candidate yields a `GoldenEntry` whose `item` is the discovered `Album`, admitted, even under a `Studio`/`PerformedBy` brief (album entries aren't gated by recording criteria).
  - an `ALBUM` candidate with no album found yields a rejected entry (`"no album"`), `item` an `Album` built from the candidate.
  - a `TRACK` candidate still uses `recordings_for` (existing behavior unchanged).
- [ ] **Step 2 — watch fail; Step 3 — implement** the `kind` branch in `_entry`. Import `Kind` (`from .recording import Candidate, Recording, Kind`) and `Album`.
- [ ] **Step 4 — green** (full offline suite). **Commit** (verbatim): `feat(core): Curator discriminates album candidates`

---

### Task 4: live album-discovery integration tests

**Files:** Test: `tests/metadata/test_albums_live.py` (new), `@pytest.mark.integration`, skipped without creds.

- [ ] **Step 1 — write tests:**
  - MB: `MusicBrainzMetadata(musicbrainzngs).albums_for(Candidate("Traffic", "John Barleycorn Must Die", kind=Kind.ALBUM))` returns albums whose top result is titled "John Barleycorn Must Die", `mbid` set, `first_released == 1970`, artist "Traffic"; no different-artist release-group survives.
  - Discogs: `DiscogsMetadata(client).albums_for(...)` returns at least one `Album` (mbid None) without hanging (islice-bounded).
- [ ] **Step 2 — controller runs it live**; **Step 3 — confirm offline suite deselects it.**
- [ ] **Step 4 — Commit** (verbatim): `test(metadata): live album-discovery integration tests`

## Phase-3 done check
- Offline green; live test passes: "Traffic – John Barleycorn Must Die" (kind=ALBUM) discovers the right release-group (mbid 3770d5ce, 1970), different artists excluded. An album candidate now produces an `Album` golden entry end-to-end.
