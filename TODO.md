# TODO

Active bugs and cleanup. (Completed work lives in git history, not here.)

## Bugs

### 1. `TidalAlbum.year` crashes on datetime release dates — aborts a run
`domain/tidal.py:46` does `len(self.release_date)`, but `infrastructure/tidal_client.py:237`
assigns `tidal_album.release_date` straight from `tidalapi`, which is a
`datetime.datetime`, not the `Optional[str]` the field declares. Any candidate album
with a datetime release date raises `TypeError: object of type 'datetime.datetime' has
no len()` inside `QualityRanker`, killing `create_playlist_from_html`.
- Fix: normalize `release_date` to an ISO string in `_parse_tidal_album` (or make
  `year` accept `date`/`datetime`/`str`). Add a regression test with a datetime input.
- Source: real traceback (was in `notes.txt`).

### 2. `TidalConfiguration.to_dict()` KeyError on OAuth save
`application/auth.py:114-125` builds a local `oauth` dict but never assigns
`result['oauth'] = oauth`, then writes `result['oauth']['refresh_token']` → `KeyError:
'oauth'` whenever a refresh token / expiry / user_id is present. OAuth credential
persistence cannot work. (This is the legacy `cli.py` auth stack — see Cleanup #1.)

## Matching quality

### 3. Cross-source metadata drift defeats exact match
Example (from `notes.txt`): *Hildegard Von Bingen — O Jerusalem*, recommended
"Sequentia Ensemble (1995)".
- Performer name differs: Scaruffi "Sequentia **Ensemble**" vs Discogs/Tidal
  "Sequentia".
- Year differs by source: Scaruffi 1995, Discogs 1997, Tidal 1998 — outside the
  ±1 (Tidal, `domain/tidal.py:73`) and ±2 (Discogs, `domain/discogs.py:64`) tolerances,
  so it matches on neither.
- Consider: fuzzier performer matching (strip "Ensemble/Quartet/Choir" suffixes),
  treating year as a soft ranking signal rather than a hard filter, or widening
  tolerances. Needs a small corpus of known-hard cases before tuning.

## Cleanup (deferred — this pass was tooling + docs only)

### 1. Two disconnected entry points / auth+config stacks
- Real pipeline: `scaruffi_tidal.py` → `infrastructure/config.py` (`ConfigManager`) →
  `application/orchestrator.py`. Saves session to `tidal_session.json`.
- Legacy auth shell: `cli.py` → `application/auth.py` → `domain/auth.py`. Its
  `process_scaruffi_url()` (`cli.py:186`) is a stub that never calls the orchestrator;
  saves session to a *different* file (`session.json`).
- Decide: fold the useful auth-strategy code into the main path, or delete the legacy
  stack. They currently share no config and no session file.

### 2. Flat package layout pollutes global imports
`domain/`, `application/`, `infrastructure/` are installed as top-level packages.
Move under `src/scaruffi_tidal/` and rewrite imports in a dedicated refactor (touches
every module + tests).

### 3. Config schema drift — pick one
- `infrastructure/config.py`: `discogs.*`, `tidal.*`, `matching.threshold`.
- `application/auth.py`: top-level `session` / `oauth` / `match_threshold` /
  `country_code`.
- The orchestrator ignores `matching.*` entirely and uses the `--min-score` CLI flag
  (default 0.3); `config.match_threshold` is dead. Settle on a single schema and make
  the CLI honor it.

### 4. SQLite cache is implemented but never wired in
`infrastructure/cache_manager.py` is complete and both clients accept a
`cache_manager`, but `scaruffi_tidal.py` never constructs or passes one — so caching
(and the "subsequent runs ~30s" behavior) never happens. Wire it up with a cache-path /
`--no-cache` option, or remove the dead code.

### 5. Rate limiter `release()` loosens the effective rate
`infrastructure/rate_limiter.py:96-108` overwrites `_last_update = now` without
re-leaking, partially discarding throttle accounting across a request. Minor; verify
against the 60 req/min Discogs limit.
