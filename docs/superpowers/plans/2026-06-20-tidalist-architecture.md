# Tidalist Architecture & Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-found `scaruffi_tidal` as a domain-modelled tool that turns a *playlist intent* — from either Scaruffi's page or a natural-language brief produced by a Claude Code agent — into a verified, human-reviewable Tidal playlist.

**Architecture:** Ports-and-adapters with a pure, I/O-free DDD domain core. Both front-ends (Scaruffi parse, NL/agent) produce the same `Candidate`s + a `Brief` (the policy). One shared core resolves each candidate to a Tidal `Track` (ISRC-first), enriches it with a `Recording` from a `MetadataProvider`, judges it against the brief's `Criterion`s, and assembles `Proposal`s a human reviews; a `Publisher` writes accepted proposals to Tidal as a `Playlist`. One repo, layered packages; the `MetadataProvider` interface is the seam we could later split out.

**Tech Stack:** Python 3.12 (uv), `tidalapi` (Catalog), `discogs-client` + MusicBrainz (Metadata), `pytest`. The domain layer is stdlib-only.

## Global Constraints

- **uv only**; run via `uv run`, never activate a venv. `requires-python = ">=3.9"`; dev pinned 3.12.
- **Domain layer (`core/`) is pure:** no network, no I/O, no third-party imports. Value objects are `@dataclass(frozen=True, slots=True)`.
- **Abstraction:** outbound deps are `typing.Protocol` ports (`Catalog`, `MetadataProvider`); criteria/ranking are Protocols too. Composition over inheritance — no ABC hierarchies. The core imports no adapter.
- **DDD:** name the domain concept, not the code role. Behavior lives on the owner (`Recording.performs`, `Brief.judge`, `Playlist.track_ids`). Ubiquitous language = the glossary below.
- **TDD:** red → green → refactor; watch every test fail first; assert real values; no over-mocking (use in-memory fakes of the ports).
- **Errors:** explicit hierarchy (`CatalogError`, `MetadataError`, `ResolutionError`); no bare `except`; no silent swallow in core.
- **Presentation stays in the CLI layer.**

## Gating decisions (resolved — proceeding under these)

1. **Name:** `tidalist` (provisional; reversible).
2. **Integration shape:** agent-driven CLI + library; Claude Code is the brain calling `resolve`/`review`/`publish`. MCP wrapper deferred.
3. **Metadata:** Discogs first (conform existing client), MusicBrainz second.
4. **Repo:** single repo, layered packages. Split `core` out only once it has a second consumer.
5. **Phase 0 minimized:** add `src/tidalist/` alongside the legacy code and make both importable via pytest `pythonpath`; defer the disruptive project rename / legacy quarantine until Phase 7, so the 52 legacy tests stay green throughout.

## Bounded contexts

1. **Intent** — *what* goes in the playlist. Inbound adapters `scaruffi` (parse) and `nl` (agent) → `Candidate`s + `Brief`.
2. **Catalog** — Tidal: playable tracks, playlist create/edit. Port `Catalog`.
3. **Metadata** — facts about a recording. Port `MetadataProvider`; adapters Discogs, MusicBrainz.
4. **Curation** — resolve + enrich + judge + assemble + review + publish. The application core.

Dependency direction: `scaruffi`, `nl`, `cli` → `core` ← (implemented by) `tidal`, `metadata` adapters.

## Ubiquitous language (glossary)

- **Candidate** — a described item to find: a track (or whole album), with whatever is known (artist, title, album, year, ISRC, `whole_album`).
- **Recording** — the abstract performance identity (keyed by **ISRC**), distinct from a **Release** (edition) and a catalog **Track** (a playable Tidal item). Carries `performance` (studio/live/…), `credits`, `first_released`. Answers "is it a cover?" / "is it live?".
- **Performance** — how the recording was made: `STUDIO | LIVE | SESSION | DEMO | UNKNOWN`. A property of the *recording* (a live take is a different ISRC).
- **Edition** — how a *release* presents a recording: `ORIGINAL | COMPILATION | SINGLE | REISSUE | SOUNDTRACK | UNKNOWN`. A property of the **Track**'s release, not the recording.
- **Credit** — `(artist, role)` on a recording.
- **Criterion** — a hard admissibility rule (Specification): `violation(recording) -> str | None`. Named, composable, positive (`PerformedBy`, `Studio`). No `Not` combinator — negation lives in structure/ranking.
- **Verdict** — admitted, or rejected with violation reasons (collected across criteria).
- **Ranking** — soft ordering for *under-specified* candidates only: `key(recording, track) -> tuple`. `PreferOriginal` leans studio + original-edition + earliest year. A **tiebreaker**, applied below ISRC and album-match in the resolver — so an iconic live take the agent pinned (e.g. *Unplugged* "Layla") is never demoted.
- **Brief** — the policy object (replaces the bag-of-flags "Preferences"): `name`, `criteria: tuple[Criterion, ...]`, `ranking: Ranking`. Behavior: `judge(recording) -> Verdict`, `rank_key(recording, track) -> tuple`.
- **Provenance** — where a candidate came from (`scaruffi` raw line, or `nl` rationale).
- **Proposal** — a candidate after resolution: `candidate`, `track: Track | None`, `recording: Recording | None`, `verdict`, `provenance`. The unit a human/agent reviews. (Rejected proposals are never Playlist members.)
- **Playlist** — the published result: `name`, ordered `track_ids`, optional Tidal id/url. "Draft" = simply not-yet-published (a lifecycle state), not a separate type.

## Resolver precedence (the live-vs-original rule)

For each candidate, pick the catalog track by precedence — ranking is only the last resort:

1. **ISRC** present → `catalog.track_by_isrc` (exact recording; definitive).
2. **Album/version named** (`candidate.album`) → prefer hits on that release (lets the agent pin a specific edition/live version).
3. **Ranking tiebreaker** → `brief.rank_key(recording, track)` among otherwise-equivalent hits (default leans original studio, earliest year).

"Iconic live" knowledge is the LLM's (it pins the version via `album`/`isrc`); the ranking stays a dumb objective default.

## PlaylistSpec (serializable hand-off; agent ↔ human)

The NL agent emits `name`+`criteria`+`proposals[].candidate`; `resolve` fills `track`/`recording`/`verdict`; the human edits; `publish` consumes accepted proposals. Criteria are a discriminated union (`{"type": "...", ...}`) — closed, validated, never `eval`'d.

```json
{
  "name": "Steve Winwood — essentials",
  "criteria": [{"type": "performed_by", "artist": "Steve Winwood"}],
  "ranking": {"type": "prefer_original"},
  "proposals": [
    {"candidate": {"artist": "Traffic", "title": "John Barleycorn",
                   "album": "John Barleycorn Must Die", "year": 1970,
                   "isrc": null, "whole_album": false},
     "provenance": {"source": "nl", "note": "signature Traffic track, Winwood lead vocal"},
     "track": null, "recording": null,
     "verdict": {"admitted": true, "violations": []}}
  ]
}
```

## Package / file structure

```
src/tidalist/
  core/
    identifiers.py   ISRC, TrackId, PlaylistId (NewType)
    errors.py        TidalistError, CatalogError, MetadataError, ResolutionError
    recording.py     Performance, Credit, Recording, Candidate
    catalog.py       Edition, Track, Album
    criteria.py      Criterion (Protocol), PerformedBy, Studio, Verdict
    ranking.py       Ranking (Protocol), PreferOriginal
    brief.py         Brief (judge, rank_key)
    proposal.py      Provenance, Proposal
    ports.py         Catalog, MetadataProvider (Protocols)
    resolve.py       Resolver (precedence; enrich; judge)
    curate.py        Curator, Publisher
    spec.py          to_spec / from_spec (PlaylistSpec)
  tidal/      session.py, catalog.py (TidalCatalog)            [Phase 2]
  metadata/   discogs.py, musicbrainz.py, rate_limit.py, cache.py [Phase 3]
  scaruffi/   parse.py, canon.py                                [Phase 6]
  nl/         spec helpers                                      [Phase 5]
  cli.py                                                        [Phase 5]
tests/
  core/   (pure, fast)        fakes.py (FakeCatalog, FakeMetadataProvider)
```

## Phase map (strangler; each phase ships working, testable software)

| Phase | Delivers | Tests |
|---|---|---|
| **1 (now)** | **Pure domain core + fake-backed Resolver/Curator/Publisher + spec round-trip** | unit + fakes, no network |
| 2 | `TidalCatalog` (ISRC add, **datetime→int year normalization + regression test**) | integration |
| 3 | `DiscogsMetadata` (conform existing) + `MusicBrainzMetadata` → `Recording` | integration |
| 4 | One `authenticate()` + one `AppConfig`; delete dual auth stacks; Discogs-only limiter; cache wire-or-cut | unit + integration |
| 5 | NL front-end: CLI `resolve`/`review`/`publish` over PlaylistSpec | e2e (fakes) + integration |
| 6 | Scaruffi front-end → `Candidate`+`Brief`; migrate parser tests; drop quality_ranker | unit + integration |
| 7 | Project rename, delete `_legacy/`, finalize README + KB | suite green |

Phases 2–7 expand into their own `writing-plans` docs at execution — adapter code depends on real API response shapes that must be probed first.

---

## Phase 1 — Pure domain core (executing in-session, TDD)

Built test-first module by module under `tests/core/`. Each module: write its tests → `uv run pytest …` (watch red) → implement → green. Authoritative code lives in `src/tidalist/core/`; signatures below are the contract.

- [ ] **Task 1 — recording.py:** `Performance(StrEnum)`; `Credit(artist, role)`; `Recording(isrc, performance, credits, first_released)` with `is_live()`, `performs(artist)`; `Candidate(artist, title, album=None, year=None, isrc=None, whole_album=False)` with `search_query()`. Tests: studio/live flags, `performs` case-insensitive + cover rejection, query composition, empty-field validation.
- [ ] **Task 2 — catalog.py:** `Edition(StrEnum)`; `Track(id, title, artists, isrc=None, album=None, year=None, edition=Edition.UNKNOWN, duration_s=None)` with `primary_artist` + **`year` must be `int|None` (TypeError otherwise — the structural fix for the legacy datetime crash)**; `Album(...)`. Tests: primary_artist, non-int year rejected, empty-artists rejected.
- [ ] **Task 3 — criteria.py:** `Verdict(admitted, violations)` with `ok()`/`rejected(*reasons)`; `Criterion(Protocol).violation(recording)`; `PerformedBy(artist)` (violation when not in performer credits → "likely a cover"); `Studio()` (violation when live). Tests: each criterion's pass/violation.
- [ ] **Task 4 — ranking.py:** `Ranking(Protocol).key(recording, track)`; `PreferOriginal()` → `(0 if original else 1, year)`, treating `Recording.is_live()`/`Track.edition` and `first_released`/`Track.year`. Tests: original studio sorts before live and later reissue.
- [ ] **Task 5 — brief.py:** `Brief(name, criteria, ranking)` with `judge(recording) -> Verdict` (collect non-None violations across criteria) and `rank_key(recording, track)` (delegate to ranking). Tests: admits when all criteria pass, rejects accumulating reasons, rank delegation.
- [ ] **Task 6 — proposal.py:** `Provenance(source, note="")`; `Proposal(candidate, track, recording, verdict, provenance)` with `admissible` (track present AND verdict admitted). Tests: the three admissibility combinations.
- [ ] **Task 7 — ports.py + tests/fakes.py:** `Catalog`/`MetadataProvider` Protocols; `FakeCatalog(tracks)` (search, `track_by_isrc`, `create_playlist`, `add_tracks`) and `FakeMetadataProvider(recordings)`. Test: fake finds by ISRC.
- [ ] **Task 8 — resolve.py + errors.py:** `Resolver(catalog, metadata=None).resolve(candidate, brief, provenance) -> Proposal` implementing the precedence (ISRC → album-match → ranking), enrich via metadata (fallback `Recording` from track when absent), judge via `brief`. Tests: ISRC resolution, cover rejection, prefer-original tiebreak, pinned-album beats ranking, no-match → rejected.
- [ ] **Task 9 — curate.py:** `Curator(resolver).draft(brief, candidates, source) -> list[Proposal]`; `Publisher(catalog).publish(name, proposals) -> PlaylistId` (admitted, de-duped, ordered; raise `CatalogError` if none). Tests: only admitted tracks published; dedup/order.
- [ ] **Task 10 — spec.py:** `to_spec(brief, proposals) -> dict` / `from_spec(dict) -> (Brief, list[Proposal])`, criteria as a discriminated union with a small closed registry. Tests: round-trip preserves criteria, candidates, verdicts.

**Phase 1 done** = the full intent→propose→publish path runs end-to-end against fakes, no network.

## Phases 2–7 — task specs (expand into own plans)

*(Carried from prior design; unchanged in substance.)*

- **Phase 2 (Tidal):** `TidalCatalog(Catalog)` over tidalapi 0.8.11; map `media.Track` → core `Track`, **normalizing `release_date` datetime → int year in the adapter** (unit test feeds a datetime → no crash); `add_by_isrc`; no rate limiter (tidalapi self-throttles). Probe search/result shapes before writing field maps.
- **Phase 3 (Metadata):** `DiscogsMetadata` (reuse legacy search/match; map format descriptors → `Performance`/`Edition`, master year → `first_released`, credits → `Credit`) wrapped in a simple min-interval limiter (Discogs has no self-throttle — verified); `MusicBrainzMetadata` (recording → ISRC, first-release-date, artist relationships → credits).
- **Phase 4 (Auth/config):** delete `_legacy` auth (`domain/auth.py`, `application/auth.py`) — removes the `to_dict` KeyError bug; `tidal/session.py::authenticate(config)` (~30 lines over tidalapi); one `AppConfig` (single YAML schema, one session file).
- **Phase 5 (NL/CLI):** idempotent JSON-in/out verbs `resolve`/`review`/`publish`; presentation here only.
- **Phase 6 (Scaruffi):** re-home parser → `parse(html) -> list[(Candidate, Brief, Provenance)]` (recommended performer → `PerformedBy`, year pinned); migrate 11 parser tests to pytest; retire the global quality_ranker.
- **Phase 7:** project rename, delete `_legacy/`, final suite green, README + KB update.

## Test strategy

- **Unit (Phase 1):** pure, ms, no I/O — the bulk of confidence. Cover happy + error/edge (cover rejection, no-match, dedup, spec round-trip).
- **Application (fakes):** Resolver/Curator/Publisher on in-memory port fakes — behavior specs, not mock mirrors.
- **Integration (Phases 2–3):** real services, `@pytest.mark.integration`, skipped by default (`uv run pytest -m "not integration"`).
- **Regression:** datetime crash (Phase 2 test); OAuth `to_dict` (obviated by Phase 4 deletion).
