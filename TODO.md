# TODO

Active work and open items. Completed work lives in git history; architecture and
phase status live in `docs/superpowers/plans/2026-06-20-tidalist-architecture.md`.

## Open

### Uniform best-effort realize across all fidelity axes (the big next design)
**Status (2026-06-23):** Slice 1 landed on branch `uniform-realize-slice-1` — the uniform
`realize_distance` / `Facet` / `choose` / `PlatformCandidate` / typed-`Compromise` framework
(`core/fidelity.py`) plus `IdentityFacet` + `EditionFacet`, with edition selection migrated
onto it. Behavior-preserving: Mr. Fantasy still resolves to the 10-track original (offline
306 green + live edition proof green). Remaining: slice 2 (recording facets +
no-silent-substitution), slice 3 (track-level album fallback — Trout Mask Replica fixture),
slice 4 (quality-preference depth). Spec:
`docs/superpowers/specs/2026-06-23-uniform-realize-design.md`; plan:
`docs/superpowers/plans/2026-06-23-uniform-realize-slice-1.md`.

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
