# tidalist

Curate a platform-agnostic **golden playlist of recordings**, then **realize** it
onto a platform (Tidal now; Spotify / local files later).

Two decoupled stages:

1. **Golden** — an intent (a natural-language brief from an agent, or Scaruffi's
   classical page) becomes candidates; metadata providers (MusicBrainz, Discogs)
   discover which recordings exist; a brief discriminates; the result is an ordered,
   persisted **golden playlist of recordings** — the durable product.
2. **Realize** — each golden recording is mapped best-effort to a playable item on a
   platform, producing a playlist plus a gap report for anything unavailable.

The golden playlist is platform-agnostic JSON: switch metadata providers, or render
the same golden onto another platform, without re-curating. Platform availability
never prunes curation — it is reported as gaps.

## Install

Requires [uv](https://docs.astral.sh/uv/) and Python ≥ 3.11.

```bash
uv sync
```

## Configure

A single XDG config file (override the base with `XDG_CONFIG_HOME`):

```bash
mkdir -p ~/.config/tidalist
cat > ~/.config/tidalist/config.yaml <<'EOF'
musicbrainz:
  contact: "you@example.com"    # MusicBrainz requires a contact in the User-Agent
discogs:
  token: "your_discogs_token"   # optional
  rate_limit: 60                # requests/minute
EOF
```

Tidal uses OAuth on the first `realize`/`publish` (a `link.tidal.com` URL to
approve); the session is cached at `~/.config/tidalist/tidal_session.json`.

## Use

The pipeline is a set of verbs over JSON artifacts. Run via the `tidalist` command
(after `uv sync`) or `uv run python -m tidalist`.

```bash
# 1. Produce an intent from Scaruffi's classical page
uv run tidalist scaruffi examples/classical.html -o intent.json
#    (or hand-write / agent-generate intent.json — see the contract below)

# 2. Curate the golden playlist (discovers recordings, applies the brief)
uv run tidalist curate intent.json -o golden.json

# 3. Review the verdicts (what was admitted / rejected, and why)
uv run tidalist review golden.json

# 4. Resolve onto Tidal — see resolved tracks + gaps, no write
uv run tidalist realize golden.json

# 5. Create the Tidal playlist
uv run tidalist publish golden.json

# Or chain curate -> realize -> publish:
uv run tidalist run intent.json -o golden.json
```

### Intent JSON

The hand-off a front-end (an agent, or `tidalist scaruffi`) produces:

```json
{
  "name": "Steve Winwood — essentials",
  "brief": {
    "criteria": [{"type": "performed_by", "artist": "Steve Winwood"}]
  },
  "candidates": [
    {"artist": "Traffic", "title": "John Barleycorn Must Die",
     "year": 1970, "note": "signature Traffic record"}
  ]
}
```

`criteria` are a closed, validated tag union — model output is never eval'd. Each
`note` becomes that entry's provenance rationale.

## Architecture

Ports & adapters around a pure, I/O-free domain core.

```
src/tidalist/
  core/       domain: recording, catalog, criteria, ranking, brief, golden,
              realize (Realizer port + Realization), spec (JSON), ports, errors
  metadata/   MetadataProvider adapters: musicbrainz, discogs (+ rate_limit)
  realize/    Realizer adapters: tidal (composes the Catalog port)
  tidal/      Tidal Catalog adapter + OAuth session
  nl/         the agent intent contract (parse_intent)
  scaruffi/   Scaruffi classical-page front-end (parse)
  cli.py      verbs: scaruffi, curate, review, realize, publish, run
  config.py   AppConfig
```

- **MetadataProvider** (`recordings_for`) feeds the golden stage: providers discover
  recordings, the Curator discriminates via the brief.
- **Realizer** (`resolve` + `emit`) feeds the realize stage: the Tidal realizer
  composes a Catalog. Spotify / local-file realizers are drop-in later — the port is
  ready; impls are built on demand.
- The domain core is stdlib-only frozen value objects; adapters never leak into it.

## Develop

```bash
uv run pytest -m "not integration"   # fast offline suite
uv run pytest                        # includes integration tests (need creds)
```

## Credits

Recommendations by Piero Scaruffi (scaruffi.com); metadata from MusicBrainz and
Discogs; streaming via Tidal.
