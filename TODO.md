# TODO

Active work and open items. Completed work lives in git history; architecture and
phase status live in `docs/superpowers/plans/2026-06-20-tidalist-architecture.md`.

## Open

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
