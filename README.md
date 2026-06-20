# Scaruffi → Tidal

Generate a Tidal playlist from Piero Scaruffi's classical-music recommendations.
The tool parses Scaruffi's HTML, optionally resolves each work to an exact release
via Discogs, searches Tidal, ranks candidates by a quality heuristic (canonical
performers/labels over raw popularity), and builds the playlist.

> Status: working end-to-end via `scaruffi_tidal.py`. Known bugs and cleanup tasks
> are tracked in [TODO.md](TODO.md) — read it before a long run (notably the
> `TidalAlbum.year` crash that can abort matching).

## Requirements

- [uv](https://docs.astral.sh/uv/) (manages Python and dependencies)
- A Discogs API token (optional but strongly recommended for exact matching) —
  https://www.discogs.com/settings/developers
- A Tidal account (OAuth login happens on first run)

## Setup

```bash
uv sync                     # creates .venv (Python 3.12), installs deps
```

Configure the Discogs token (XDG path, override with `XDG_CONFIG_HOME`):

```bash
mkdir -p ~/.config/scaruffi-tidal
cat > ~/.config/scaruffi-tidal/config.yaml <<'EOF'
discogs:
  token: "your_discogs_token_here"
  rate_limit: 60          # requests/minute (default 60)
EOF
```

Without a token the run continues Tidal-only (less accurate; no exact matches).

## Usage

```bash
# From a local file (download Scaruffi's page first)
curl -o classical.html https://www.scaruffi.com/music/classica.html
uv run scaruffi-tidal classical.html

# Or pass a URL directly
uv run scaruffi-tidal https://www.scaruffi.com/music/classica.html
```

First run opens an OAuth flow (a `link.tidal.com` URL to approve). The session is
saved to `~/.config/scaruffi-tidal/tidal_session.json` and reused afterward.

### Options

| Flag | Default | Effect |
|------|---------|--------|
| `--name NAME` | "Scaruffi: A Recommended Discography…" | Playlist name |
| `--min-score N` | `0.3` | Minimum quality score (0.0–1.0) to include a match |
| `--no-discogs` | off | Skip Discogs (faster, less accurate) |
| `--config PATH` | XDG default | Alternate config file |
| `--verbose` / `-v` | off | DEBUG logging |

`scaruffi-tidal` is the installed entry point; `uv run python scaruffi_tidal.py …`
is equivalent.

## How it works

```
Scaruffi HTML
  └─ parse ─────────────▶ ScaruffiEntry (composer, work, performer, year, label, alternates)
       └─ Discogs lookup ▶ DiscogsRelease (authoritative metadata, for exact match)
            └─ Tidal search ▶ up to 50 TidalAlbum candidates
                 └─ rank ────▶ best album by quality score
                      └─ add ▶ Tidal playlist
```

### Quality score

```
if exact match to the Discogs release:   score = 1.0
else:  score = 0.50 * canonical_performer   # Karajan, Gardiner, Gould, …
             + 0.35 * canonical_label        # DG, Decca, ECM, …  (see note)
             + 0.15 * normalized_popularity  # tiebreaker
```

A match is kept only if `score >= --min-score`. If the primary recording yields no
match, the entry's alternate recordings are tried in order.

> **Note:** Tidal search results don't expose a label, so the 35% label weight is
> currently inert in practice. Canonical lists live in `domain/canonical.py`.

## Architecture

Clean/onion layering; dependencies point inward.

```
infrastructure/  ── external systems (HTML parser, Discogs/Tidal clients, config,
                    rate limiter, SQLite cache)
application/     ── use cases (QualityRanker, PlaylistOrchestrator)
domain/          ── frozen value objects (Recording, DiscogsRelease, TidalAlbum,
                    ScaruffiEntry) + canonical performer/label sets
scaruffi_tidal.py ─ CLI entry point (full pipeline)
```

Domain objects are immutable (frozen dataclasses) and have no infrastructure deps.

## Development

```bash
uv sync                                              # sync deps + dev group
uv run python -m unittest discover -s tests -p "test_*.py"   # 52 tests
uv run pytest                                        # same tests via pytest
```

Tests are layered to match the architecture (`tests/domain`, `tests/application`,
`tests/infrastructure`).

## Known limitations

- **Album granularity.** Matching is per-album; a classical album may bundle works
  beyond the recommended one.
- **Discogs rate limit.** 60 req/min is the bottleneck (~4–5 min minimum for the
  ~270-entry page).
- **Tidal labels.** Not exposed in search → label weight unused (above).
- **Interactive OAuth.** First Tidal login needs a browser.

See [TODO.md](TODO.md) for active bugs and structural cleanup (e.g. the duplicate
`cli.py`/`application/auth.py` auth stack, the unused cache wiring).

## Credits

Recommendations by Piero Scaruffi (scaruffi.com); metadata from Discogs; streaming
via Tidal.
