# Albums Phase 1 — Domain model + `Album | Recording` golden unit

> **For agentic workers:** execute task-by-task with TDD (red→green→refactor; watch each test fail first). Steps use checkbox (`- [ ]`). This is Phase 1 of `docs/superpowers/plans/2026-06-21-albums-and-identity.md` — read its Key Decisions and Ubiquitous Language. Pure domain, **no API/network**. Branch: `albums-first`.

**Goal:** The golden playlist can hold **album** entries as well as recordings, end-to-end through the domain + JSON serialization. No discovery/realize behavior yet (the Curator still produces Recording entries; album curation is Phase 3, album realize is Phase 5).

## Global Constraints

- uv only; `uv run pytest -m "not integration" -q` must stay green. `requires-python >=3.11`.
- Domain pure: no I/O, no third-party imports. Value objects `@dataclass(frozen=True, slots=True)`.
- TDD: write the failing test, watch it fail for the right reason, minimal impl, green, commit.
- DDD: terse intention-revealing names. Match existing style in `src/tidalist/core/`.
- Each task ends offline-green and is committed.

---

### Task 1: `Kind` enum + `Candidate.kind` (replaces `whole_album`)

**Files:**
- Modify: `src/tidalist/core/recording.py` (add `Kind`; swap `Candidate.whole_album` → `kind`)
- Modify: `src/tidalist/core/spec.py` (`_candidate_to_dict`/`_candidate_from_dict`)
- Modify: `src/tidalist/scaruffi/parse.py` (`whole_album=True` → `kind=Kind.ALBUM`)
- Modify: `src/tidalist/nl/intent.py` (contract docstring: `"whole_album": false` → `"kind": "track"`)
- Test: `tests/core/test_recording.py`, `tests/core/test_spec.py`, `tests/scaruffi/test_parse.py`, and any intent fixtures using `whole_album` (`tests/test_cli.py`, `tests/nl/test_intent.py` — grep `whole_album` and update all)

**Interfaces:**
- Produces: `Kind(StrEnum)` with `ALBUM = "album"`, `TRACK = "track"`. `Candidate(artist, title, album=None, year=None, isrc=None, kind=Kind.TRACK)`. The intent/candidate JSON field is `"kind"` (string `"album"`/`"track"`), default `"track"`.

- [ ] **Step 1 — failing test** (`tests/core/test_recording.py`):
```python
from tidalist.core.recording import Kind
def test_candidate_kind_defaults_to_track():
    assert Candidate("Traffic", "Glad").kind is Kind.TRACK
def test_candidate_can_be_an_album():
    assert Candidate("Traffic", "John Barleycorn Must Die", kind=Kind.ALBUM).kind is Kind.ALBUM
```
- [ ] **Step 2 — watch fail:** `uv run pytest tests/core/test_recording.py -q` → ImportError/AttributeError on `Kind`/`kind`.
- [ ] **Step 3 — implement:** add `class Kind(StrEnum): ALBUM = "album"; TRACK = "track"` to `recording.py`; replace `Candidate.whole_album: bool = False` with `kind: Kind = Kind.TRACK`.
- [ ] **Step 4 — propagate:** `spec.py` `_candidate_to_dict` emits `"kind": c.kind.value` (remove `whole_album`); `_candidate_from_dict` reads `kind=Kind(d.get("kind", "track"))`. `scaruffi/parse.py` sets `kind=Kind.ALBUM` (drop `whole_album=True`). `nl/intent.py` docstring updated. Update every test referencing `whole_album` (grep it) to `kind`.
- [ ] **Step 5 — green:** `uv run pytest -m "not integration" -q` all pass.
- [ ] **Step 6 — commit:** `feat(core): Candidate.kind (album|track) replaces whole_album`

---

### Task 2: `Album` value object

**Files:**
- Create: `src/tidalist/core/album.py`
- Modify: `src/tidalist/core/catalog.py` (remove the unused `Album` class + its mention in the module docstring)
- Test: Create `tests/core/test_album.py`; Modify `tests/core/test_catalog.py` (remove the `Album` test/import)

**Interfaces:**
- Produces: `Album(artist: str, title: str, mbid: MBID | None = None, first_released: int | None = None)` — frozen/slots; release-group identity. (Edition fields arrive in Phase 4; do not add them now — YAGNI.)

- [ ] **Step 1 — failing test** (`tests/core/test_album.py`):
```python
from tidalist.core.identifiers import MBID
from tidalist.core.album import Album
def test_album_carries_identity_fields():
    a = Album(artist="Traffic", title="John Barleycorn Must Die",
              mbid=MBID("rg-1"), first_released=1970)
    assert a.artist == "Traffic" and a.title == "John Barleycorn Must Die"
    assert a.mbid == "rg-1" and a.first_released == 1970
def test_album_optional_fields_default_none():
    a = Album(artist="Blind Faith", title="Blind Faith")
    assert a.mbid is None and a.first_released is None
```
- [ ] **Step 2 — watch fail:** `uv run pytest tests/core/test_album.py -q` → ModuleNotFoundError.
- [ ] **Step 3 — implement** `core/album.py` with the frozen dataclass above (import `MBID` from `.identifiers`).
- [ ] **Step 4 — remove dead `catalog.Album`:** delete the `Album` class from `catalog.py` and the `Album` import+test in `tests/core/test_catalog.py`. Confirm nothing else imports `catalog.Album` (`grep -rn "catalog import.*Album\|catalog.Album" src tests`).
- [ ] **Step 5 — green:** `uv run pytest -m "not integration" -q`.
- [ ] **Step 6 — commit:** `feat(core): Album value object (release-group identity); drop unused catalog.Album`

---

### Task 3: `GoldenEntry.item: Album | Recording`

**Files:**
- Modify: `src/tidalist/core/golden.py` (`GoldenEntry.recording` → `item`; Curator constructs Recording items as today)
- Modify: `src/tidalist/core/realize.py` (`e.recording` → `e.item`; resolve only `Recording` items, `Album` items → gap for now)
- Modify: `src/tidalist/cli.py` (`format_golden`/`format_realization` use `.item`; tolerate `Album` which has no `performance`)
- Test: `tests/core/test_golden.py`, `tests/core/test_realize.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `Album` (Task 2), `Recording`.
- Produces: `GoldenEntry(item: Album | Recording, provenance: Provenance, verdict: Verdict)` — first positional arg is now `item`. `RealizedEntry`/`Realization` unchanged in shape. In `realize()`, an admitted entry whose `item` is an `Album` resolves to `None` (a gap) until Phase 5.

- [ ] **Step 1 — failing tests:**
  - `tests/core/test_golden.py`: assert `golden.entries[0].item` (not `.recording`) for an existing curate test.
  - `tests/core/test_realize.py`: add — an admitted `GoldenEntry` whose `item` is an `Album` yields a gap (no resolve attempted). Example:
```python
from tidalist.core.album import Album
def test_album_entry_is_a_gap_until_phase_5():
    g = _golden(GoldenEntry(Album(artist="Traffic", title="John Barleycorn Must Die"),
                            Provenance("nl"), Verdict.ok()))
    r = realize(g, _FakeRealizer({}))
    assert [e.golden.item.title for e in r.gaps()] == ["John Barleycorn Must Die"]
```
- [ ] **Step 2 — watch fail.**
- [ ] **Step 3 — implement:** rename `GoldenEntry.recording` → `item` (type `Album | Recording`); the field stays the first positional, so `GoldenEntry(chosen, provenance, verdict)` in `golden.py` is unchanged. In `realize.py`: `RealizedEntry(e, realizer.resolve(e.item) if isinstance(e.item, Recording) else None)` (import `Recording`). In `cli.py`: `.recording` → `.item`; make `_recmeta` use `getattr(item, "performance", None)` so `Album` (no performance) is tolerated.
- [ ] **Step 4 — propagate** every `.recording` reference on a `GoldenEntry`/`RealizedEntry.golden` in src + tests (`grep -rn "\.recording" src tests` and fix the golden-entry ones; leave `Proposal`/Track `.recording`-unrelated alone — there are none after the cleanup).
- [ ] **Step 5 — green:** `uv run pytest -m "not integration" -q`.
- [ ] **Step 6 — commit:** `feat(core): GoldenEntry.item is Album | Recording`

---

### Task 4: kind-tagged golden-entry serialization

**Files:**
- Modify: `src/tidalist/core/spec.py` (`_golden_entry_to_dict`/`_golden_entry_from_dict`)
- Test: `tests/core/test_spec.py`

**Interfaces:**
- Consumes: `Album` (Task 2), `GoldenEntry.item` (Task 3).
- Produces: a golden entry dict tagged `"kind": "album" | "track"`. Track entries keep today's flattened recording fields plus `"kind": "track"`. Album entries serialize `{"kind": "album", "mbid", "artist", "title", "year", "provenance", "verdict"}` (`year` = `album.first_released`). `from_golden` round-trips both.

- [ ] **Step 1 — failing test** (`tests/core/test_spec.py`): a `GoldenPlaylist` with one `Recording` entry and one `Album` entry round-trips through `to_golden`/`from_golden` equal; assert the album entry dict has `"kind": "album"` and `"mbid"`.
```python
def test_golden_round_trips_album_and_track_entries():
    brief = Brief("Winwood", ())
    track = GoldenEntry(Recording(artist="Traffic", title="Glad", mbid=MBID("r1"),
                                  first_released=1970, performance=Performance.STUDIO),
                        Provenance("nl"), Verdict.ok())
    album = GoldenEntry(Album(artist="Traffic", title="John Barleycorn Must Die",
                              mbid=MBID("rg1"), first_released=1970),
                        Provenance("nl", "whole album"), Verdict.ok())
    g = GoldenPlaylist("Winwood", brief, (track, album))
    assert from_golden(to_golden(g)) == g
    dicts = to_golden(g)["entries"]
    assert dicts[0]["kind"] == "track" and dicts[1]["kind"] == "album"
    assert dicts[1]["mbid"] == "rg1"
```
- [ ] **Step 2 — watch fail** (album entry serialized as a recording / round-trip unequal).
- [ ] **Step 3 — implement:** `_golden_entry_to_dict` branches on `isinstance(e.item, Album)`: album → `{"kind":"album","mbid":a.mbid,"artist":a.artist,"title":a.title,"year":a.first_released,...prov,verdict}`; recording → existing dict plus `"kind":"track"`. `_golden_entry_from_dict` branches on `d.get("kind","track")`: `"album"` builds `Album(...)`, else builds the `Recording` as today.
- [ ] **Step 4 — green:** `uv run pytest -m "not integration" -q`.
- [ ] **Step 5 — commit:** `feat(spec): kind-tagged golden entries (album | track) round-trip`

---

## Phase-1 done check

- `uv run pytest -m "not integration" -q` green.
- A `GoldenPlaylist` can hold and JSON-round-trip both `Album` and `Recording` entries; `Candidate.kind` drives album-vs-track intent; `Album` realizes as a gap (Phase 5 wires real album realization). Curator still produces Recording entries (Phase 3 adds album curation).
