# TODO

Active work and open items. Completed work lives in git history.

The codebase is being re-founded as `tidalist` (`src/tidalist/`) per
`docs/superpowers/plans/2026-06-20-tidalist-architecture.md`. The legacy code
(`domain/`, `application/`, `infrastructure/`, `scaruffi_tidal.py`) is still
present and gets deleted in Phase 7.

## Open

### Live integration unverified (Phases 2-3)
The Tidal and Discogs/MusicBrainz adapters are unit-tested against fakes anchored
to probed signatures, but not run against the real APIs. Once `authenticate()`
plus `musicbrainzngs.set_useragent` give a live session, confirm: Tidal
`SearchResults` shape and `playlist.add` on a fresh playlist; discogs result
shape (formats/year/artists); musicbrainzngs response shapes. Add
`@pytest.mark.integration` tests.

### Matching quality: cross-source drift
Hard case from the old run: Hildegard Von Bingen "O Jerusalem", recommended
"Sequentia Ensemble (1995)", vs Discogs 1997 / Tidal 1998, performer "Sequentia".
The new design mitigates it (`Recording.performs` substring-matches "Sequentia"
within "Sequentia Ensemble"; year is a ranking signal, not a hard filter), but
validate against a corpus of known-hard cases before trusting it.

### Phase 7: delete legacy
Remove `domain/`, `application/`, `infrastructure/`, `scaruffi_tidal.py`,
`classical.html` and their tests once the scaruffi + nl front-ends (Phases 5-6)
replace them. Retires, in one go, the old `TidalAlbum.year` datetime bug, the
dead SQLite cache, the over-built leaky-bucket limiter, and the dual config
schema (all superseded by tidalist).
