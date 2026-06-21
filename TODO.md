# TODO

Active work and open items. Completed work lives in git history; architecture and
phase status live in `docs/superpowers/plans/2026-06-20-tidalist-architecture.md`.

## Open

### Rename the repo to match the package
The package, distribution, and CLI are all `tidalist`, but the GitHub repo and local
dir are still `scaruffi_tidal`. Rename `cehbz/scaruffi_tidal` → `cehbz/tidalist`
(GitHub rename + update the git remote URL; optionally rename `~/projects/scaruffi_tidal`).

### Live integration unverified
The adapters are unit-tested against fakes anchored to probed signatures, but the
full pipeline is not end-to-end verified against real APIs. With a live Tidal
session (`authenticate()`) and `musicbrainzngs.set_useragent`, confirm and add
`@pytest.mark.integration` tests for: MusicBrainz `search_recordings` hit shapes
feeding `recordings_for`; the `TidalRealizer` resolve/emit path (search,
`get_tracks_by_isrc`, create + add on a fresh playlist); Discogs result shapes.

### Classical whole-work vs track granularity, and cross-source drift
Scaruffi recommends whole works (album-length), but the golden/realize pipeline runs
at recording/track granularity. `scaruffi/parse.py` candidates carry
`whole_album=True`, but nothing consumes it yet — decide how realization handles a
whole-album candidate (resolve to an album, expand to tracks, or a dedicated
album-realize path). Validate matching against a corpus of hard cases (e.g. the
old Sequentia "O Jerusalem": recommended "Sequentia Ensemble (1995)" vs Discogs 1997
/ Tidal 1998 / performer "Sequentia").
