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

### Cross-source edition/identity drift on classical whole works
The album path itself is built: Scaruffi whole-work recommendations become
`kind=Kind.ALBUM` candidates, the golden carries Album units, and the Tidal realizer
expands an album to its tracks. What remains is matching *reliability* — validate
identity/edition matching against a corpus of hard cases where sources disagree
(e.g. the old Sequentia "O Jerusalem": recommended "Sequentia Ensemble (1995)" vs
Discogs 1997 / Tidal 1998 / performer "Sequentia").
