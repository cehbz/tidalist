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

- **Candidate** — a described item to find (artist, title, album?, year?, isrc?, whole_album?). From the LLM/Scaruffi.
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
  "brief": {"criteria": [{"type": "performed_by", "artist": "Steve Winwood"}],
             "ranking": {"type": "prefer_original"}},
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

**Phase B done, offline-green (166 passed, 1 skipped):** `golden.py` (`GoldenEntry`, `GoldenPlaylist`, `Curator`) — the Curator discovers recordings per candidate and discriminates via the brief (criteria admit/reject, then a recording-ranking picks the best, preferring admissible takes); a miss or all-rejected candidate still yields a reviewable entry with a rejected verdict. New `RecordingRanking` + `PreferStudioEarliest` (track-free; prefer studio then earliest) — the golden ranking, chosen as a Curator default arg, *not* yet carried on the `Brief` (the plan's "does Brief carry both rankings" stays deferred; trivially movable later). The existing `PreferOriginal` (edition/realize ranking) is untouched for the transitional `Resolver`. `Provenance` moved to its own `provenance.py` (re-exported from `proposal.py`) so `golden.py` doesn't depend on legacy code. `spec.py` gains `to_golden`/`from_golden` (flattened entry, `year` key, credits for fidelity) round-tripping the durable artifact. **Resume at Phase C** (Realizer port + Tidal realizer). **Last commit is Phase A (`ae9a6f0`); Phase B is uncommitted.**

Live verification (read paths): **Tidal ✓** (real search; datetime→int year confirmed on live data; `track_by_isrc` works), **Discogs ✓** (`formats` shape matches; year correct), **MusicBrainz: selection defect** — `search_recordings(limit=1)` + `[0]` grabbed a live bootleg (tied score-100 hits) with no ISRC/date. This is *superseded* by the golden-first redesign: MB returns `recordings_for` (a list) and the Curator discriminates via the brief; no in-adapter pick.

The current application layer (`Resolver`, `Proposal`, `PlaylistDraft`, `Curator`/`Publisher`, `resolve.py`/`curate.py`) was built for early Tidal resolution and **reshapes** into the golden Curator + the Realizer. The domain value objects (Recording, Track, Candidate, Criterion, Ranking, Brief, Verdict, Provenance) mostly survive; `Recording` gains the identity-bundle fields.

## Phases (revised)

**Done (Phases 1-4):** core value objects; Tidal adapter (`track_from_tidal` datetime→int fix + `TidalCatalog`); Discogs + MusicBrainz adapters; `AppConfig`, `authenticate()`, `MinInterval`. Legacy auth trio deleted.

**Forward:**

- **A. Metadata returns candidates. ✅ DONE.** `MetadataProvider.recordings_for(candidate) -> list[Recording]`; MB returns all search hits (cheap, no `[0]` pick, ISRC enriched lazily in B), Discogs returns all releases (mapper takes the candidate for title/artist). `Recording` gained `mbid` + `title/artist/album/duration_s`; `MBID` identifier added; `spec.py` round-trips them. `Resolver` carries a transitional first-of-list pick until the Curator replaces it.
- **B. Golden stage. ✅ DONE.** `golden.py`: `GoldenEntry` / `GoldenPlaylist` / `Curator` (discover per candidate → criteria admit/reject → `PreferStudioEarliest` recording-ranking picks among admissible). Misses and all-rejected candidates yield reviewable rejected entries; realization filters to admitted. `RecordingRanking` + `PreferStudioEarliest` added to `ranking.py`; `Provenance` extracted to `provenance.py`; `spec.py` `to_golden`/`from_golden` persist the portable artifact. Recording-ranking is a Curator default (not on `Brief`) — the "Brief carries both rankings" question stays deferred.
- **C. Realizer port + Tidal realizer.** Define `Realizer`; fold today's `TidalCatalog` into `realize/tidal.py` (resolve by ISRC then closeness; emit = create playlist + add). Produce `Realization` + gaps.
- **D. NL front-end + CLI.** Agent-driven verbs over the golden + realization artifacts: build golden from a brief, review, realize, publish. Presentation here only.
- **E. Scaruffi front-end.** Re-home the parser → `(Candidate, Brief)` producers; migrate parser tests; drop `quality_ranker`.
- **F. More realizers (on demand).** Spotify (API/ISRC); local/VLC (tag-index scan via mutagen/TinyTag; write M3U8/XSPF). Port is ready; impls are YAGNI until wanted.
- **G. Cleanup.** Delete legacy (`domain/`, `application/`, `infrastructure/`, `scaruffi_tidal.py`, `classical.html`) and its tests; reconsider the project name; finalize README + KB.

## Test strategy

Pure-domain unit tests (ms, no I/O) carry the bulk. Application use cases tested against in-memory port fakes. Adapter integration tests marked `@pytest.mark.integration`, skipped without creds (`uv run pytest -m "not integration"`), live-verified on demand. Regressions: the datetime→int Tidal fix has a test; MB selection gets one once `recordings_for` lands.
