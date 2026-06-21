# Albums Phase 2 — Provider identity matching (recordings)

> Execute task-by-task with TDD. Phase 2 of `2026-06-21-albums-and-identity.md`. Branch `albums-first`. **Live-verify-first** — shapes below were probed against real MusicBrainz on 2026-06-21.

**Goal:** `MusicBrainzMetadata.recordings_for` returns only recordings that are genuinely the candidate's artist — resolve the candidate's artist string to a MusicBrainz **artist MBID**, then keep only hits credited to that MBID. Fixes the live "Traffic – Glad → Traffic Sound – I'm So Glad" mismatch. Identity is the provider's job; the brief's quality criteria stay in the Curator.

## Probed MusicBrainz shapes (anchor fakes to these)

- `mb.search_artists(artist="Traffic", limit=N)` → `{"artist-list": [{"id", "name", "disambiguation", "type", "ext:score"}, …]}`. Top result is the band Traffic (`9fadfba9-…`, score `"100"`); "Traffic Sound" is a *distinct* artist (`239ce544-…`, score `"76"`). Take the top (first) hit.
- A `search_recordings` hit's `"artist-credit"` is `[{"artist": {"id": "<mbid>", "name": "…"}}, " feat. ", …]`. Keep the hit iff some credit entry's `artist.id` equals the resolved artist MBID.

## Global Constraints

uv only; `uv run pytest -m "not integration" -q` green. Domain pure. Adapter unit-tested against a fake `mb` anchored to the shapes above; live behavior covered by a `@pytest.mark.integration` test (Task 3), skipped without creds. Match `src/tidalist/metadata/musicbrainz.py` style.

---

### Task 1: resolve a candidate's artist to a MusicBrainz artist MBID

**Files:**
- Modify: `src/tidalist/metadata/musicbrainz.py` (add `_artist_mbid`)
- Test: `tests/metadata/test_musicbrainz.py`

**Interfaces:**
- Produces: a method `MusicBrainzMetadata._artist_mbid(self, artist: str) -> str | None` — calls `self._mb.search_artists(artist=artist, limit=self._artist_limit)` (add `_artist_limit: int = 5` in `__init__`), returns the first hit's `"id"`, or `None` if no hits. The existing `_FakeMB` test double gains a `search_artists(self, artist="", limit=None, **kw)` returning `{"artist-list": self._artists}`.

- [ ] **Step 1 — failing test** (extend `_FakeMB` to take an `artists` list and add `search_artists`; then):
```python
def test_artist_mbid_returns_top_hit_id():
    mb = _FakeMB([], artists=[{"id": "a-traffic", "name": "Traffic"},
                              {"id": "a-sound", "name": "Traffic Sound"}])
    assert MusicBrainzMetadata(mb)._artist_mbid("Traffic") == "a-traffic"
def test_artist_mbid_none_when_no_hits():
    assert MusicBrainzMetadata(_FakeMB([], artists=[]))._artist_mbid("Nobody") is None
```
- [ ] **Step 2 — watch fail** (`_artist_mbid`/`search_artists` missing).
- [ ] **Step 3 — implement:** `__init__` gains `artist_limit: int = 5` → `self._artist_limit`. Add:
```python
def _artist_mbid(self, artist: str) -> str | None:
    hits = self._mb.search_artists(artist=artist, limit=self._artist_limit).get("artist-list") or []
    return hits[0]["id"] if hits else None
```
- [ ] **Step 4 — green:** `uv run pytest tests/metadata/test_musicbrainz.py -q`, then full offline suite.
- [ ] **Step 5 — commit** (message verbatim): `feat(metadata): resolve a candidate's artist to a MusicBrainz artist MBID`

---

### Task 2: recordings_for keeps only identity-matched recordings

**Files:**
- Modify: `src/tidalist/metadata/musicbrainz.py` (`recordings_for`; add a credit-match helper)
- Test: `tests/metadata/test_musicbrainz.py`

**Interfaces:**
- Consumes: `_artist_mbid` (Task 1).
- Produces: `recordings_for` resolves the candidate's artist MBID, then keeps only search hits credited to it. **Fallback:** if `_artist_mbid` returns `None` (artist unresolved), return all hits unfiltered (degrade gracefully, don't drop everything). A hit with no `artist-credit` is dropped only when an MBID was resolved.

- [ ] **Step 1 — failing test:**
```python
def _hit_credited(rec_id, artist_id, artist_name):
    return {"id": rec_id, "title": "Glad", "length": "419000",
            "artist-credit": [{"artist": {"id": artist_id, "name": artist_name}}],
            "release-list": [{"id": "r", "title": "John Barleycorn Must Die", "date": "1970"}],
            "disambiguation": ""}
def test_recordings_for_drops_hits_not_credited_to_the_resolved_artist():
    mb = _FakeMB([_hit_credited("rec-traffic", "a-traffic", "Traffic"),
                  _hit_credited("rec-sound", "a-sound", "Traffic Sound")],
                 artists=[{"id": "a-traffic", "name": "Traffic"}])
    recs = MusicBrainzMetadata(mb).recordings_for(Candidate("Traffic", "Glad"))
    assert [r.mbid for r in recs] == ["rec-traffic"]   # Traffic Sound dropped
def test_recordings_for_unfiltered_when_artist_unresolved():
    mb = _FakeMB([_hit_credited("rec-1", "a-x", "X")], artists=[])  # no artist match
    assert len(MusicBrainzMetadata(mb).recordings_for(Candidate("X", "Glad"))) == 1
```
- [ ] **Step 2 — watch fail** (both Traffic + Traffic Sound currently returned).
- [ ] **Step 3 — implement:** in `recordings_for`, after getting `hits`, resolve `artist_mbid = self._artist_mbid(candidate.artist)`; if it's not None, `hits = [h for h in hits if _credited_to(h, artist_mbid)]`. Add:
```python
def _credited_to(rec: dict, artist_mbid: str) -> bool:
    return any(isinstance(e, dict) and (e.get("artist") or {}).get("id") == artist_mbid
               for e in rec.get("artist-credit") or [])
```
- [ ] **Step 4 — green:** full offline suite. Existing `recordings_for` tests still pass (their fakes have no `artists`, so resolution returns None → unfiltered → unchanged behavior). Verify.
- [ ] **Step 5 — commit** (verbatim): `feat(metadata): recordings_for returns only identity-matched recordings`

---

### Task 3: live MusicBrainz identity-matching integration test

**Files:**
- Test: `tests/metadata/test_musicbrainz_live.py` (new)

**Interfaces:** consumes the real `musicbrainzngs` + config. Marked `@pytest.mark.integration`; skipped when `musicbrainz.contact` is unset.

- [ ] **Step 1 — write the integration test:**
```python
import pytest, musicbrainzngs
from tidalist.config import AppConfig
from tidalist.core.recording import Candidate
from tidalist.metadata.musicbrainz import MusicBrainzMetadata

@pytest.mark.integration
def test_traffic_glad_excludes_traffic_sound_live():
    cfg = AppConfig.load()
    if not cfg.musicbrainz_contact:
        pytest.skip("no musicbrainz.contact configured")
    musicbrainzngs.set_useragent("tidalist", "1.0", cfg.musicbrainz_contact)
    recs = MusicBrainzMetadata(musicbrainzngs).recordings_for(Candidate("Traffic", "Glad"))
    assert recs, "expected Traffic 'Glad' recordings"
    artists = {r.artist for r in recs}
    assert all("Traffic Sound" not in a for a in artists)   # the bug we fixed
    assert any(a == "Traffic" for a in artists)
```
- [ ] **Step 2 — run it live** (controller will run `uv run pytest -m integration tests/metadata/test_musicbrainz_live.py -q`); confirm it passes against real MusicBrainz.
- [ ] **Step 3 — confirm it's skipped in the offline suite:** `uv run pytest -m "not integration" -q` does not run it.
- [ ] **Step 4 — commit** (verbatim): `test(metadata): live MusicBrainz identity-matching integration tests`

## Phase-2 done check
- Offline suite green; the live test passes and confirms "Traffic – Glad" yields Traffic recordings with Traffic Sound excluded.
- `recordings_for` is now identity-scoped; the golden Curator (Phase 1/3) ranks only genuine matches.
