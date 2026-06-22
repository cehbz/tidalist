# Albums-First & Identity Matching — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement task-by-task. Steps use checkbox (`- [ ]`) syntax. This plan **evolves** the built golden-then-realize architecture — read `docs/superpowers/plans/2026-06-20-tidalist-architecture.md` first; the vocabulary and ports there are assumed.

**Goal:** Make **albums first-class alongside recordings** in the golden playlist, move **identity matching into the metadata provider**, and model **edition** as a first-class, tunable concern — so a single requirement-dense intent (the Steve Winwood north-star below) produces a correct mixed album/track golden playlist.

**Architecture:** The golden unit becomes `Album | Recording`. The **provider** identity-matches (returns the *right things*, using structured MB identity, not fuzzy search noise); the **Curator/brief** applies *quality* (criteria + ranking). An **Album** is identified by its **release-group** (edition-agnostic); **edition** splits into a brief criterion + a per-entry/standing preference + a realize-time resolver. The **NL agent selects** (world knowledge: "best albums", "fan favorite", "significant member"); the **tool verifies + resolves** (performs-not-cover, edition, identity, platform match).

**Tech Stack:** Python 3.11+ (uv); `musicbrainzngs` (release-groups, artist identity, recordings), `discogs-client` (masters/releases — edition attributes), `tidalapi`; `pytest`. Domain layer stdlib-only.

## Global Constraints

- uv only; run via `uv run`. `requires-python >=3.11` (StrEnum).
- Domain (`core/`) is pure: no I/O, no third-party imports. Value objects are `@dataclass(frozen=True, slots=True)`.
- Outbound deps are `typing.Protocol` ports (consumer-defined). Core imports no adapter.
- DDD ubiquitous language; behavior on the owning object. Terse docstrings: state what exists.
- TDD red→green→refactor; watch each test fail first; fakes over mocks.
- Structured errors; no bare `except`; presentation only in the CLI layer.
- **Adapters are live-verify-first for this work:** before authoring an adapter task that depends on a real API shape (MB release-group / artist-identity, Discogs master/release attributes, Tidal album resolution), probe the live shape and anchor the fakes to it. The Discogs pagination hang (found 2026-06-21: `recordings_for` walked every lazily-paginated page) is the cautionary tale — fakes returning plain lists hid it.

## North-star acceptance test (verbatim user intent)

> "I want a playlist of Steve Winwood's greatest music. His best albums, including groups where he was a significant member not just his solo work, as well as individual tracks where he either made a significant contribution, is known for that track, or it's a fan or artist favorite. Include only performances where he's performing (except when including entire albums), not covers. Prefer original recordings to live, compilation, or re-releases."

Decomposition (this drives the whole design — every row must be satisfiable):

| Phrase | Maps to |
|---|---|
| "best albums … as well as individual tracks" | **Album \| Recording**, mixed in one playlist |
| "groups where he was a significant member" (Traffic, Blind Faith, Spencer Davis) | identity on **Winwood-the-person** (one artist MBID) found in *credits across band names* — not a band-name string match |
| "best / known for / fan or artist favorite / significant contribution" | **agent selection** (world knowledge) → candidates + provenance notes; not tool-verifiable |
| "only performances where he's performing … not covers (**except entire albums**)" | performer/cover check is a **track-scoped** criterion, *waived for album entries* |
| "prefer original to live, compilation, re-release" | **edition preference**, default original |

This intent becomes the canonical end-to-end fixture (`tests/fixtures/winwood_intent.json`), referenced by Phase 6.

## Key decisions (this evolution)

1. **Golden unit = `Album | Recording`.** A golden entry references one or the other. An **Album entry is identity only** (release-group + metadata + edition preference); its tracklist is *derived at realize*, never stored in the golden (Tidal flattening is a platform restriction, not the golden's shape).
2. **Identity matching is the provider's job, not the Curator's.** `recordings_for` / `albums_for` return only items that genuinely *are* the candidate (right artist, right work) — via structured MB identity (artist/release-group MBIDs), not substring matching. *Quality* discrimination (brief criteria + ranking) stays in the Curator. This corrects the original "providers never pick": finding the right *thing* (identity) ≠ picking the best *version* (quality). It fixes the live-found bug where "Traffic – Glad" resolved to "Traffic Sound – I'm So Glad".
3. **Album identity = release-group; edition = a release under it.** MB release-group / Discogs master = "the album"; a release/version (original, SW remix, MoFi, reissue) = an edition. This cleanly separates *which album* from *which edition*.
4. **Edition is three cooperating pieces:**
   - a **brief criterion** (hard): exclude compilations / live albums ("studio albums only");
   - an **edition preference** (soft): default = canonical-tracklist + original mastering; a **standing provenance policy** that prefers **Steven Wilson** editions (baked-in default), then others (e.g. MoFi), over original; **per-entry override** wins over the standing policy. Two orthogonal axes: *tracklist integrity* (vs padded reissues) and *mastering provenance* (who remastered/remixed).
   - a **realize-time resolver**: pick the best *available* edition on the target; **compromise and report** when the preferred edition is absent.
5. **Criteria scope by entry kind, attached per-candidate.** Track entries carry track-level criteria (performs / not-cover); album entries don't ("except entire albums"). The agent attaches the right criteria to each candidate, since it already decides the kind and holds the world knowledge. (Album-level rules like "significant member" are agent *selection*, not mechanical criteria.)
6. **Agent selects, tool verifies + resolves.** "Greatest / best / fan-favorite / significant member" are world-knowledge judgments the agent makes (candidates + notes). The brief is only the small, *verifiable* core (performs-not-cover, edition, studio). Identity verification ("Winwood is performing") needs full performer credits (MB artist-relations) — the lazy-credit fetch deferred in the 2026-06-20 plan is now required.
7. **Discogs flips to primary for album/edition metadata.** Release/master-level was "wrong granularity" for recordings; it is exactly *right* for albums and editions (label = MoFi, format = SACD, credits = remixed-by-Steven-Wilson). MB release-groups give album identity; Discogs releases give the edition attributes to choose among.

## Ubiquitous language (additions)

- **Album** — the golden album unit: identity (release-group MBID), artist(s), title, `first_released`, edition preference. No tracklist (derived at realize).
- **Kind** — `ALBUM | TRACK`. A candidate declares which; replaces the boolean `whole_album`.
- **Edition** — a release of an album (existing `Edition` enum: ORIGINAL / COMPILATION / SINGLE / REISSUE / LIVE / SOUNDTRACK / UNKNOWN), now lifted to album level + carrying provenance attributes (label, remixer, format).
- **EditionPreference** — per-entry soft policy: tracklist-integrity + provenance ordering.
- **EditionPolicy** — standing default preference (config): provenance ranking, default `[steven_wilson, mofi, original]`.
- **GoldenEntry.item** — `Album | Recording` (was `Recording`).
- **Realization compromise** — a resolved entry whose edition differs from the preferred one (reported, not a gap).

## Phases (each shippable; metadata phases are live-verify-first)

> **Status:** Phases 1–6 complete on branch `albums-first` (per-phase task plans in `2026-06-21-albums-phase-{1..6}.md`). Offline suite green; the full curate → realize → publish pipeline live-verified end-to-end (a real Tidal playlist created from a live-MusicBrainz album curation, with the Steven-Wilson edition default reported as a compromise when Tidal could not honor it). The Winwood north-star runs as the offline acceptance test (`tests/test_winwood_acceptance.py`).

Detailed bite-sized TDD tasks are authored per phase **at execution time** (after live-probing the relevant API shapes). Each phase ends **offline-green AND live-checked against the real API** (see Test strategy) and is independently reviewable.

**Phase 1 — Album domain model + `Album | Recording` golden unit (pure, no API).**
Deliverable: the golden stage can hold album entries. `core/album.py` (`Album` VO, replacing the unused `catalog.Album`); `Candidate.kind` (`Kind` enum) replacing `whole_album`; `GoldenEntry.item: Album | Recording`; `spec.py` serializes album entries (`kind`-tagged); the Curator passes albums through (discrimination wired in Phase 3). Fully specifiable now — **this phase gets a detailed bite-sized plan immediately.**

**Phase 2 — Provider identity matching for recordings (live-verify MB).**
Deliverable: `recordings_for` returns only genuine candidate matches. Add an artist-resolution step (candidate artist string → MB artist MBID; optional candidate-supplied MBID hint) and filter recordings to that artist + a title match. Fixes "Traffic Sound". Carry the artist-MBID so the per-candidate cover-check (Phase 6) can verify across band names. Tunable; `@pytest.mark.integration` against live MB.

**Phase 3 — Album discovery (live-verify MB release-groups + Discogs masters).**
Deliverable: `MetadataProvider.albums_for(candidate) -> list[Album]`; MB release-groups (identity) joined with Discogs masters (edition attributes); identity-matched per Phase 2. The Curator discriminates album candidates (criteria + an album-ranking). Discogs becomes the primary album source.

**Phase 4 — Edition (criterion + preference + resolver).**
Deliverable: `Edition`-as-criterion (exclude comps/live) on the brief; `EditionPreference`/`EditionPolicy` (default original + tracklist-integrity; Steven Wilson standing default; per-entry override); the realize-time edition resolver (best available, compromise + report). Discogs release attributes (label/format/credits) drive provenance matching — live-verify their shapes.

**Phase 5 — Realize albums (live Tidal; needs auth).**
Deliverable: the `Realizer` resolves an `Album` to the platform — Tidal: find the album, expand to its tracks in order; apply edition selection; emit; report gaps and edition compromises. Recording realization unchanged.

**Phase 6 — Intent schema + front-ends + the Winwood fixture.**
Deliverable: the intent JSON gains `kind`, per-candidate criteria scope, edition prefs, and identity hints (artist MBID); `nl/intent.py` contract + `parse_intent` updated; the Scaruffi front-end sets `kind=ALBUM` for classical works; the Winwood north-star intent lands as `tests/fixtures/winwood_intent.json` and an end-to-end acceptance test (curate → review → realize against fakes anchored to live shapes).

## Test strategy

**Live/functional/e2e testing is interleaved early and per-phase — not saved for the end.** It has already caught two bugs unit tests could not (the Discogs pagination hang; the "Traffic → Traffic Sound" mismatch), so every phase ends with offline-green *and* a live check, and the north-star is exercised end-to-end as soon as it is runnable.

- Pure-domain unit tests carry the bulk (Phase 1, edition-policy logic); fakes are anchored to **live-probed** shapes, not guessed.
- **Per-phase live checkpoint** (`@pytest.mark.integration`, skipped without creds), each a small real call eyeballed before the phase is "done":
  - Phase 2 — re-run the live "Traffic – Glad" curate; confirm it resolves to *Traffic's* Glad, not Traffic Sound.
  - Phase 3 — live album curate; a known album resolves to the right release-group.
  - Phase 4 — live edition resolution against a release with known label/format/credits.
  - Phase 5 — create one small, disposable real Tidal playlist and eyeball it.
- **Run the Winwood north-star as a partial e2e as early as it is runnable** (curate against live MB once Phase 2/3 land), deepening as phases complete — do not wait for Phase 6 to first touch it.
- Each live finding becomes an offline regression test anchored to the observed shape: Discogs pagination bound (done), identity-match (Phase 2), album round-trip (Phase 1).

## Open / tunable (not first-cut blockers)

- **Artist-resolution reliability** (string → MB artist MBID can be ambiguous). Start simple, tune; allow a candidate-supplied MBID to bypass it.
- **"Remaster sometimes better"** — a popularity/reputation override on original-preference. Wire the hook, default off.
- **Release-group leak** — when MB/Discogs promotes a version to its own release-group (true remix album / radical deluxe), the "album = release-group" abstraction needs a per-entry release(-group) pin escape hatch. Exception, not the model.

## Future signal sources (out of scope — captured so it's not lost)

The ranking/selecting mill needn't lean only on raw popularity. Glenn McDonald's **Every Noise at Once** (an ex-Spotify project; updates appear to have largely stopped after his 2023 layoff) generated Spotify's algorithmic genre playlists — canonically **"The Sound of X"** (most representative / core), **"The Pulse of X"** (popular now), **"The Edge of X"** (most distinctive / outlier) — i.e. the user's "heart of / edge of" framing: a *representative ↔ distinctive* axis orthogonal to popularity. Those playlists may still be queryable via the Spotify API even if Every Noise itself is stale, and they're interesting grist for both **candidate selection** (what belongs) and **ranking** (which version / how central). Watch for other algorithmic sources too — audio features (energy/acousticness), editorial/critic lists, scrobble data — beyond the obvious popularity indexes. A signal-source axis for a future ranking iteration; not in scope here.
