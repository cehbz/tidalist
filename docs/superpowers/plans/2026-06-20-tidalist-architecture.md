# Tidalist Architecture & Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans to implement task-by-task. This doc was revised on 2026-06-21 to the **golden-then-realize** architecture; earlier single-stage framing is superseded.

**Goal:** From a playlist intent (NL brief via a Claude Code agent, or Scaruffi's page), curate a platform-agnostic **golden playlist of recordings**, then **realize** it best-effort onto a platform (Tidal now; Spotify / local files later).

**Architecture:** Two decoupled stages.
1. **Golden** (platform-agnostic): intent → candidates → metadata discovers which recordings exist → the brief discriminates → an ordered, persisted golden playlist of **recordings**.
2. **Realize** (per platform): map each golden recording to the closest playable item, best-effort, producing a platform playlist + a gap report.

Ports-and-adapters with a pure, I/O-free DDD core. `MetadataProvider` feeds the golden stage; `Realizer` adapters feed the realize stage; the two never touch each other.

**Tech Stack:** Python 3.12 (uv); `tidalapi`, `discogs-client`, `musicbrainzngs`; `pytest`. Domain layer is stdlib-only.

## Global Constraints

- uv only; run via `uv run`. `requires-python >=3.9`; dev pinned 3.12.
- Domain (`core/`) is pure: no I/O, no third-party imports. Value objects are `@dataclass(frozen=True, slots=True)`.
- Outbound deps are `typing.Protocol` ports (consumer-defined; Go-style structural). Core imports no adapter.
- DDD ubiquitous language (glossary below); behavior on the owning object. Terse docstrings: state what exists, not rejected alternatives.
- TDD red→green→refactor; watch each test fail first; fakes over mocks.
- Structured errors; no bare `except`; no silent swallow in core. Presentation stays in the CLI layer.
- Adapters are unit-tested against fakes anchored to probed real signatures, then live-verified.

## Key decisions (durable)

1. **Golden-then-realize.** The golden playlist (recordings) is the durable product; a platform playlist is one best-effort rendering. Motivation: provider switching (has happened, will again) and rendering the same golden to a local music collection (e.g. a VLC playlist). Don't let platform availability leak into curation; report it as gaps.
2. **Two-axis model splits across stages.** *Performance* (studio/live) is a recording property → decided at the golden stage. *Edition* (original/compilation/reissue) is a release property → decided at realization (which track/release of the chosen recording).
3. **Golden entry identity is a bundle, keyed by MBID.** `MBID` (MusicBrainz Recording ID) primary + `ISRC` (the cross-platform realization bridge) + `artist/title/album/year/duration` (fuzzy fallback). Rationale: the golden unit is a *recording*, and only MusicBrainz models recordings as first-class entities with IDs and ISRCs; Discogs is release/master-level (wrong granularity). Optional Discogs release ID as an edition reference.
4. **Metadata providers discover, they don't pick.** `recordings_for(candidate) -> list[Recording]`. Discrimination (which recording) is the brief's job in the golden Curator, not the adapter's.
5. **Providers by strength.** MusicBrainz: recording identity, ISRC, performer credits, live flag. Discogs: edition metadata (format descriptors Live/Compilation, label) for the realization/edition axis. Both publish full data dumps; the `MetadataProvider` port lets a local mirror replace the live API (the user plans local copies to avoid rate limits) with no design change.
6. **Realizer port generalizes the Tidal `Catalog`.** A Realizer: resolves a recording to a platform item (ISRC-first, then closeness), and emits a playlist. Streaming = API match + create/add; local = tag-index scan + write M3U8/XSPF. Build the Tidal realizer now; Spotify/local are drop-in later (port designed for them; impls are YAGNI until needed).
7. **Project name** `tidalist` is provisional and now arguably misleading (Tidal is one realizer of several). Reconsider at Phase G.

## Bounded contexts

1. **Intent** — what goes in the playlist. Adapters: `nl` (agent), `scaruffi` (parse). Output: `Candidate`s + a `Brief`.
2. **Metadata** — which recordings exist + their facts. Port `MetadataProvider`; adapters MusicBrainz, Discogs.
3. **Golden curation** — candidates + metadata + brief → an ordered golden playlist of recordings.
4. **Realization** — golden + a platform → playable tracks + gaps. Port `Realizer`; adapters Tidal (now), Spotify/local (later).

## Ubiquitous language (glossary)

- **Candidate** — a described item to find (artist, title, album?, year?, isrc?, kind=album|track, per-candidate criteria?, edition?, artist_mbid?). From the LLM/Scaruffi. *(The albums-first evolution replaced the original `whole_album?` flag with `kind`; see `2026-06-21-albums-and-identity.md`.)*
- **Recording** — the golden unit: a specific performance. Identity bundle: `mbid`, `isrc`, `performance`, `credits`, `first_released`, plus title/artist/album/duration for fallback. (Currently `recording.py` lacks `mbid`/title/artist/album/duration — add them.)
- **Performance** — STUDIO / LIVE / SESSION / DEMO / UNKNOWN. Recording axis.
- **Edition** — ORIGINAL / COMPILATION / SINGLE / REISSUE / LIVE / SOUNDTRACK / UNKNOWN. Release axis, lives on a realized track.
- **Credit** — (artist, role). `Recording.performs(artist)` = the cover check.
- **Criterion** — hard admissibility rule (Specification): `violation(recording) -> str | None`. `PerformedBy`, `Studio`. Positive names, no `Not` combinator.
- **Verdict** — admitted, or rejected with reasons.
- **Ranking** — soft ordering. Likely splits: a recording-ranking (golden: prefer studio, earliest) and a track/edition-ranking (realize: prefer original release). TBD whether the `Brief` carries both.
- **Brief** — policy: name + criteria + ranking. `judge(recording) -> Verdict`, `rank_key(...)`.
- **GoldenPlaylist** — name + brief + ordered golden entries (recordings + provenance + verdict). The durable, persisted, portable artifact (JSON; see below).
- **Realization / Rendering** — a golden mapped onto one platform: per-entry resolved track (or gap) + match quality. Naming TBD (`GoldenPlaylist`+`Realization` vs `Playlist`+`Rendering`).
- **Provenance** — where a candidate came from (`scaruffi` line / `nl` rationale).

## Golden artifact (persisted JSON)

The durable product; portable across realizers.

```json
{
  "name": "Steve Winwood — essentials",
  "brief": {"criteria": [{"type": "performed_by", "artist": "Steve Winwood"}]},
  "entries": [
    {"mbid": "…", "isrc": "GB…", "artist": "Traffic", "title": "John Barleycorn",
     "album": "John Barleycorn Must Die", "year": 1970, "duration_s": 386,
     "performance": "studio",
     "provenance": {"source": "nl", "note": "signature Traffic track"},
     "verdict": {"admitted": true, "violations": []}}
  ]
}
```

## Ports

- `MetadataProvider.recordings_for(candidate) -> list[Recording]` — discovery; no internal selection.
- `Realizer` (per platform): `resolve(recording) -> PlatformItem | None` (ISRC-first, then closeness) and `emit(name, items) -> reference` (API create/add, or write a playlist file). Generalizes today's `Catalog`.
- Front-ends produce `(candidates, brief)` and drive the use cases.

## Package structure (target)

```
src/tidalist/
  core/        recording.py (+mbid/title/etc.), catalog.py (Track/Edition), criteria.py,
               ranking.py, brief.py, golden.py (GoldenPlaylist, Curator), realize.py
               (Realization, Realizer port), spec.py (golden JSON), ports.py, errors.py,
               identifiers.py
  metadata/    musicbrainz.py, discogs.py, rate_limit.py
  realize/     tidal.py (TidalRealizer; wraps today's TidalCatalog ops)   [local/, spotify/ later]
  nl/          spec/agent helpers
  scaruffi/    parse.py
  cli.py       verbs: curate (build golden), review, realize, publish
  config.py    AppConfig
tests/         mirror; core/ pure + fast; adapter integration marked @pytest.mark.integration
```

## Status (2026-06-21)

Phases 1-4 committed (last commit `c3d6e5c`). **Phase A done, offline-green (151 passed, 1 skipped):** `Recording` carries the identity bundle (`mbid` + `artist/title/album/first_released/duration_s` + `isrc/performance/credits`); `MBID` identifier added; `MetadataProvider.recordings_for(candidate) -> list[Recording]` — MB and Discogs return every hit, no in-adapter pick. MB discovery is cheap (one search, no per-hit `get_recording_by_id`); ISRC stays `None` at discovery and is enriched lazily once a recording is chosen (Phase B). Discogs is release-level, so its mapper takes the candidate for title/artist. `spec.py` round-trips the new fields. `Resolver` has a transitional first-of-list pick (marked) until the Curator lands.

**Phase B done, offline-green (166 passed, 1 skipped):** `golden.py` (`GoldenEntry`, `GoldenPlaylist`, `Curator`) — the Curator discovers recordings per candidate and discriminates via the brief (criteria admit/reject, then a recording-ranking picks the best, preferring admissible takes); a miss or all-rejected candidate still yields a reviewable entry with a rejected verdict. New `RecordingRanking` + `PreferStudioEarliest` (track-free; prefer studio then earliest) — the golden ranking, chosen as a Curator default arg, *not* yet carried on the `Brief` (the plan's "does Brief carry both rankings" stays deferred; trivially movable later). The existing `PreferOriginal` (edition/realize ranking) is untouched for the transitional `Resolver`. `Provenance` moved to its own `provenance.py` (re-exported from `proposal.py`) so `golden.py` doesn't depend on legacy code. `spec.py` gains `to_golden`/`from_golden` (flattened entry, `year` key, credits for fidelity) round-tripping the durable artifact.

**Phase C done, offline-green (177 passed, 1 skipped):** `core/realize.py` — the `Realizer` port (`resolve(recording) -> PlatformItem | None`, `emit(name, items) -> ref`) plus value objects (`PlatformItem`, `MatchQuality` = isrc/strong/weak, `RealizedEntry`, `Realization`) and two pure functions: `realize(golden, realizer)` resolves every *admitted* entry into a `Realization` (resolved + gaps, no writes) and `publish(realization, realizer)` emits the resolved items. Split so gaps are reviewable before any platform write (matches the separate realize/publish CLI verbs). `realize/tidal.py` — `TidalRealizer` *composes* a `Catalog` (reusing `TidalCatalog` unchanged, testable with `FakeCatalog`): `resolve` is ISRC-first then closest search hit (title/artist/album/duration), `emit` creates the playlist + adds refs. The `Catalog` port stays as Tidal's building block; the `Realizer` port is the cross-platform seam (local/Spotify compose other backends later). No new tidalapi surface, so live coverage rides on the already-verified `TidalCatalog`.

**Phase D done, offline-green (200 passed, 1 skipped):** `cli.py` — verbs `curate` (intent JSON → golden JSON), `review` (print verdicts), `realize` (resolve onto platform, no write), `publish` (create the playlist), and `run` (curate→realize→publish). Pure formatters (`format_golden`/`format_realization`) and DI verb functions (`curate_golden`/`realize_golden`/`publish_golden`) are fake-tested; `main(argv, *, config_loader, metadata_factory, realizer_factory, out)` injects adapters at the composition root (real builders: MB `set_useragent` + `MusicBrainzMetadata`; `authenticate`→`TidalCatalog`→`TidalRealizer`). `core/spec.py` gains `to_intent`/`from_intent` (the front-end hand-off: candidates + per-line `note` + brief). `nl/intent.py` documents the agent intent contract and validates it (`parse_intent`: name + ≥1 candidate, closed criterion union). **Per the deferred decision, `Curator.curate` now takes per-candidate `provenances`** so the agent's rationale rides into each golden entry. `python -m tidalist` works (`__main__.py`); review verb live-smoked on a real golden file. *Deferred to Phase G:* wiring the `tidalist` console script in `pyproject` (needs `src/` added to the build).

**Phase E done, offline-green (193 passed):** `scaruffi/parse.py` re-homes the classical parser to produce the intent triple `(candidates, provenances, brief)` — `artist`=performer, `title`="Composer: Work", `whole_album`, alternates → provenance note, brief with no hard criteria (Scaruffi's pick is the discrimination). New `scaruffi` CLI verb (`scaruffi page.html -o intent.json`) feeds `curate`; live-smoked HTML→intent end-to-end. Parser tests migrated to `tests/scaruffi/`. **Clean cut (per decision):** deleted the dead `quality_ranker → tidal_client → orchestrator → scaruffi_tidal.py` island + its test, and dropped the broken `scaruffi-tidal` console-script/`py-modules` from `pyproject` (no dangling import; app runs via `python -m tidalist`). The 1 prior skip (legacy real-file test) is gone with the migration.

**Phase F skipped (YAGNI, by decision):** the `Realizer` port is ready; Spotify/local realizers are built on demand — none wanted now.

**Phase G done, offline-green (162 passed):** deleted all remaining legacy (`domain/`, `application/`, `infrastructure/`) and its tests; moved the Scaruffi sample to `examples/classical.html`; finalized packaging — `pyproject` name `tidalist`, src-layout `packages.find` (`where=["src"]`), `tidalist` console script (`tidalist.cli:main`), `requires-python >=3.11` (StrEnum is the real floor, plan's `>=3.9` was wrong), dropped unused `lxml`; rewrote the README for the golden-then-realize pipeline; trimmed `TODO.md` to live-open items. Project name **kept as `tidalist`** (decided — rename churn not worth it). Console script and end-to-end `tidalist scaruffi examples/classical.html` (267 candidates) verified. (Committed `d1505ea`.)

**Post-G cleanup, offline-green (142 passed):** removed the pre-golden transitional layer that golden+realize superseded — `core/resolve.py` (Resolver), `core/curate.py` (old Curator/Publisher), `core/proposal.py` (Proposal), and `spec.py`'s `to_spec`/`from_spec` + their dead helpers — plus their tests; nothing in the live pipeline imported them. **Resolved the deferred "does the Brief carry the ranking" question by dropping it:** `Brief` = name + criteria only; the vestigial edition `Ranking`/`PreferOriginal` are deleted (the realize stage uses `TidalRealizer` closeness, the golden stage uses the Curator's `PreferStudioEarliest`). The golden/intent brief JSON is now just `{"criteria": [...]}`. **Pipeline complete (Phases 1-4, A-E, G); F is on-demand. Open work in `TODO.md`.**

Live verification (read paths): **Tidal ✓** (real search; datetime→int year confirmed on live data; `track_by_isrc` works), **Discogs ✓** (`formats` shape matches; year correct), **MusicBrainz: selection defect** — `search_recordings(limit=1)` + `[0]` grabbed a live bootleg (tied score-100 hits) with no ISRC/date. This is *superseded* by the golden-first redesign: MB returns `recordings_for` (a list) and the Curator discriminates via the brief; no in-adapter pick.

The current application layer (`Resolver`, `Proposal`, `PlaylistDraft`, `Curator`/`Publisher`, `resolve.py`/`curate.py`) was built for early Tidal resolution and **reshapes** into the golden Curator + the Realizer. The domain value objects (Recording, Track, Candidate, Criterion, Ranking, Brief, Verdict, Provenance) mostly survive; `Recording` gains the identity-bundle fields.

## Phases (revised)

**Done (Phases 1-4):** core value objects; Tidal adapter (`track_from_tidal` datetime→int fix + `TidalCatalog`); Discogs + MusicBrainz adapters; `AppConfig`, `authenticate()`, `MinInterval`. Legacy auth trio deleted.

**Forward:**

- **A. Metadata returns candidates. ✅ DONE.** `MetadataProvider.recordings_for(candidate) -> list[Recording]`; MB returns all search hits (cheap, no `[0]` pick, ISRC enriched lazily in B), Discogs returns all releases (mapper takes the candidate for title/artist). `Recording` gained `mbid` + `title/artist/album/duration_s`; `MBID` identifier added; `spec.py` round-trips them. `Resolver` carries a transitional first-of-list pick until the Curator replaces it.
- **B. Golden stage. ✅ DONE.** `golden.py`: `GoldenEntry` / `GoldenPlaylist` / `Curator` (discover per candidate → criteria admit/reject → `PreferStudioEarliest` recording-ranking picks among admissible). Misses and all-rejected candidates yield reviewable rejected entries; realization filters to admitted. `RecordingRanking` + `PreferStudioEarliest` added to `ranking.py`; `Provenance` extracted to `provenance.py`; `spec.py` `to_golden`/`from_golden` persist the portable artifact. Recording-ranking is a Curator default (not on `Brief`) — the "Brief carries both rankings" question stays deferred.
- **C. Realizer port + Tidal realizer. ✅ DONE.** `core/realize.py`: `Realizer` port (`resolve`/`emit`) + `PlatformItem`/`MatchQuality`/`RealizedEntry`/`Realization` + pure `realize` (resolve admitted → Realization + gaps, no writes) and `publish` (emit). `realize/tidal.py`: `TidalRealizer` composes a `Catalog` (reuses `TidalCatalog`; ISRC-first then closeness; emit = create + add). `Catalog` port retained as Tidal's backend.
- **D. NL front-end + CLI. ✅ DONE.** `cli.py` verbs `curate`/`review`/`realize`/`publish`/`run` (file-based + a pipeline shortcut); pure formatters + DI verb functions + `main` with injectable adapter factories. `core/spec.py` `to_intent`/`from_intent`; `nl/intent.py` validating `parse_intent` + the agent contract. `Curator.curate` revised to per-candidate `provenances` (the deferred provenance decision). `python -m tidalist` via `__main__.py`. Console-script wiring deferred to G.
- **E. Scaruffi front-end. ✅ DONE.** `scaruffi/parse.py` → intent triple (artist=performer, title="Composer: Work", whole_album, alternates→provenance, no hard criteria); `scaruffi` CLI verb emits intent JSON for `curate`; parser tests migrated to `tests/scaruffi/`. Clean cut: deleted the dead quality_ranker→tidal_client→orchestrator→scaruffi_tidal.py island + test, dropped the broken pyproject script/py-module.
- **F. More realizers (on demand). ⏸ SKIPPED (YAGNI).** Spotify (API/ISRC) and local/VLC (tag-index scan → M3U8/XSPF) remain unbuilt; the `Realizer` port is ready, built when wanted.
- **G. Cleanup. ✅ DONE.** Deleted legacy `domain/`/`application/`/`infrastructure/` + tests; moved `classical.html` → `examples/`; finalized `pyproject` (name `tidalist`, src-layout, `tidalist` console script, `requires-python >=3.11`, dropped `lxml`); rewrote README; trimmed TODO. Name kept as `tidalist`.

## Test strategy

Pure-domain unit tests (ms, no I/O) carry the bulk. Application use cases tested against in-memory port fakes. Adapter integration tests marked `@pytest.mark.integration`, skipped without creds (`uv run pytest -m "not integration"`), live-verified on demand. Regressions: the datetime→int Tidal fix has a test; MB selection gets one once `recordings_for` lands.
