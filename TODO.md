# TODO

Active work and open items. Completed work lives in git history; architecture and
phase status live in `docs/superpowers/plans/2026-06-20-tidalist-architecture.md`.

## Open

### Uniform best-effort realize across all fidelity axes (the big next design)
**Status (2026-06-23):** Slices 1–4 landed (stacked branches `uniform-realize-slice-1` →
`-slice-2` → `-slice-3` → `-slice-4`; not merged to main). Slice 1: the uniform `realize_distance` /
`Facet` / `choose` / `PlatformCandidate` / typed-`Compromise` framework (`core/fidelity.py`) +
`IdentityFacet` + `EditionFacet`, edition selection migrated onto it — behavior-preserving
(Mr. Fantasy → 10-track; offline + live edition proof green). Slice 2: `PerformanceFacet` + a
fuzzy-closeness `IdentityFacet` (ISRC as a positive exact-match signal; graded token-set title
distance + scale-invariant duration ratio); recording resolution is facet-native via `choose`
and `resolve` reports a typed compromise instead of silently substituting a live take. Slice 3:
**track-level album fallback** — when a release-group is absent on the platform, `resolve_album`
assembles the canonical tracklist track-by-track from individual catalog tracks and reports an
`album-source` compromise (counts + missing positions) instead of gapping. Proven live: Trout
Mask Replica assembles 28/28 from compilations. Also fixed `TidalPlatform.track_by_isrc` to
return `None` (not raise) for an ISRC absent from the catalog. Slice 4: a specifiable
**audio-quality tiebreak** — `choose`'s secondary sort key is now quality-aware
(`QualityPreference`: hi-res > lossy, then popularity), a *lexicographic* tiebreak below every
fidelity facet with `ref` as the final backstop (no summed "AudioFacet" — that would be
magnitude-fragile); `Track` carries observed `audio_quality` + `popularity`. Offline 331 green.
**Outstanding:** a live no-silent-substitution confirmation (slice 2) is still deferred (no stable
fixture). **Remaining (the arc's open tail — all need a rich-metadata backend or are out of
deterministic reach):** `source_kind` (original > comp) + `ReleaseClassFacet` + per-track
source-release attribution; the album-edition quality tiebreak (`PlatformAlbum` carrying quality);
and a cheap/local-LLM judge for context-dependent title/identity matching (the limit of the
deterministic string metrics). Specs in `docs/superpowers/specs/`, plans in
`docs/superpowers/plans/`.

`edition_distance` is the first slice of a general `realize_distance(golden_item,
platform_candidate)` over **identity + release-class + performance + edition**. Today
only edition is built; the other axes are resolved at curation and then either gapped
or *silently substituted* at realize — both wrong. Target model: the golden specifies a
desired value per axis; realize observes each axis best-effort on platform candidates,
picks the nearest, and emits a **compromise per axis it couldn't satisfy**; a gap is the
last resort. Concretely:
- **No silent substitution.** If the studio ISRC is absent and only a live take exists,
  resolve it but report "studio take unavailable; used a live version" (or gap if the
  brief is strict) — don't swap silently.
- **Track-level album fallback.** If a release-group is absent on the backend but its
  tracks exist on a comp/live album, assemble the canonical tracklist track-by-track and
  report the source — don't gap an obtainable album.
- **Platform observation per axis.** Best-effort read of release-class / performance on
  platform candidates (title + identity now; structured when a rich-metadata backend —
  torrent/local — lands).
- **Distance-0 tiebreak / quality-preference layer.** When candidates tie on fidelity
  (same ISRC on the original album *and* a comp; two identical pressings; FLAC vs lossy),
  break the tie by a *specifiable* secondary preference (original-source > comp, hi-res >
  lossy, popularity) — same shape as `EditionPreference`. Currently `min()` breaks ties
  by arbitrary list order (latent non-determinism). Ties into the deferred "Every Noise /
  representative-vs-distinctive / quality signals" idea.
This is its own branch + session; it may reshape the value objects (a platform candidate
gaining observed class/performance).

### Intent and curation: ordering, dedup, band-member credits

Surfaced by the live Steve Winwood end-to-end (NL brief -> agent intent -> curate):

- **Playlist ordering.** No way to specify output order. Add an ordering directive to the
  intent (e.g. the NL "ordered by decreasing best-ness" -> the agent emits an ordering the
  Curator preserves and realize/publish honor). Entries currently keep candidate order.
- **Dedup a track already on an included album.** A track whose recording sits on an album
  also in the playlist should not also appear standalone ("Higher Love" inside *Back in the
  High Life* and as a track; "The Low Spark of High Heeled Boys" as both album and track).
  Needs matching the track to an included album's tracklist at curation, and a policy for
  which wins.
- **`performed_by(member)` wrongly rejects band recordings.** MusicBrainz credits the group
  as the recording artist, not the individual member, so `performed_by("Steve Winwood")`
  rejects the original Spencer Davis Group / Traffic / Blind Faith recordings as "likely a
  cover" (only his solo tracks pass). Cover detection for a band member needs
  band-membership / relationship awareness, not just a performer-credit string match.
  (Also seen: recording selection sometimes picks a later re-recording, e.g. "I'm a Man"
  resolving to 1988, "While You See a Chance" to 1992 -- ties into the existing
  canonical-tracklist / cross-source drift item below.)
- **No per-artist caching.** Curate re-resolves the artist MBID per candidate (`_artist_mbid`
  calls `search_artists` each time) and realize re-fetches the full discography per album
  (`album_editions` -> `artist.get_albums()`), so multiple same-artist entries (four Traffic
  albums) redundantly repeat the same lookups. Memoize artist resolution and the discography
  per artist within a run; the MusicBrainz 1 req/s throttle makes this the dominant curate
  cost (the 20-candidate run took ~8 min; realize was ~35s).
- **Local backends to dodge rate limits (structural mitigation).** The `MetadataProvider` port
  already lets a local MusicBrainz/Discogs mirror (both ship full data dumps) replace the live
  API, removing the curate throttle entirely -- the bigger win. Tidal cannot be mirrored (DRM
  streaming), so the realize-side options are a persistent lookup cache (cuts repeated
  discography fetches) or the roadmapped local-file realizer (tag-index scan -> M3U8/XSPF) that
  needs no streaming API. Design is noted in the architecture plan; this surfaces it as
  actionable future work.

### Golden JSON back-compat for release traits
`Album.traits` (typed `ReleaseTrait`) replaced the old stringly-typed
`secondary_types`/`primary_type`. A golden JSON written before that change silently
reloads with `traits=frozenset()` (its comp/live classification dropped). No such files
exist in-repo; add a lenient reader (`traits` else map legacy `secondary_types`) only if
external golden files need to survive the change.

### Rename the repo to match the package
The package, distribution, and CLI are all `tidalist`, but the GitHub repo and local
dir are still `scaruffi_tidal`. Rename `cehbz/scaruffi_tidal` → `cehbz/tidalist`
(GitHub rename + update the git remote URL; optionally rename `~/projects/scaruffi_tidal`).

### Broaden committed integration-test coverage
The full curate → realize → publish pipeline is now verified live against real APIs
(a real Tidal playlist was created end-to-end from a live-MusicBrainz album curation),
and `tests/realize/test_tidal_live.py` covers the `resolve_album` path. Still worth
committing `@pytest.mark.integration` tests for the remaining live shapes: MusicBrainz
`search_recordings` feeding `recordings_for`; the recording `resolve`/`emit` path; and
Discogs result shapes — so regressions in adapter parsing are caught, not just the
album realize path.

### Canonical-tracklist selection reliability, and cross-source drift
Edition *selection* is now built and live-verified: the golden carries MusicBrainz's
canonical tracklist, and the realizer enumerates editions via the artist discography
and picks the one of minimum distance to it (Mr. Fantasy resolves to the 10-track
original, not the 22-track deluxe). Two reliability gaps remain:
- **Which release is canonical?** `_canonical_tracklist` picks the earliest *standard*
  (modal-track-count) official release. For works with divergent national editions
  (the US "Heaven Is in Your Mind" vs UK "Mr. Fantasy" tracklists) this is a real
  editorial call — the chosen reference decides what "nearest" means. Tunable; validate
  against a corpus.
- **Cross-source drift** on hard cases where sources disagree (e.g. the old Sequentia
  "O Jerusalem": recommended "Sequentia Ensemble (1995)" vs Discogs 1997 / Tidal 1998).
- Edition-distance **weights** (`core/realize.py`) are first-cut constants; the
  `year=None` penalty bound and the dominance invariant are domain-bounded, not proven
  (see the P2 plan's noted minors). Revisit if real playlists misselect.
- The `num_tracks` **coarse-shortlist** (skip fetching tracks for editions far off the
  golden's track count) was dropped for simplicity — `resolve_album` fetches every
  edition's tracks, and `CatalogAlbum.num_tracks` is currently unconsumed. Add the
  shortlist if some artist's discography proves deep enough to matter.
- `tidal/catalog.py` `album_editions` swallows all exceptions (broad `except`) to honor
  the realizer's `or survivors` fallback; narrow it if it ever masks a real bug.
- `_track_matches` (ISRC-present-on-ref-but-absent-on-track → title fallback) is correct
  but lacks a dedicated unit test.
