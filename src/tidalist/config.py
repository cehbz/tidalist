"""Single application configuration, loaded from one XDG YAML file."""

import os
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class AppConfig:
    config_dir: Path
    discogs_token: str | None = None
    discogs_rate_limit: int = 60
    musicbrainz_contact: str | None = None

    @property
    def session_file(self) -> Path:
        return self.config_dir / "tidal_session.json"

    @property
    def mb_cache_dir(self) -> Path:
        """On-disk store for the MusicBrainz request cache (resumable curate backstop)."""
        return default_cache_path() / "mb"

    @classmethod
    def load(cls, path: Path | None = None) -> "AppConfig":
        path = path or default_config_path()
        data = {}
        if path.exists():
            data = yaml.safe_load(path.read_text()) or {}
        discogs = data.get("discogs") or {}
        musicbrainz = data.get("musicbrainz") or {}
        return cls(
            config_dir=path.parent,
            discogs_token=discogs.get("token"),
            discogs_rate_limit=discogs.get("rate_limit", 60),
            musicbrainz_contact=musicbrainz.get("contact"),
        )


def default_config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    base = Path(base) if base else Path.home() / ".config"
    return base / "tidalist" / "config.yaml"


def default_cache_path() -> Path:
    base = os.environ.get("XDG_CACHE_HOME")
    base = Path(base) if base else Path.home() / ".cache"
    return base / "tidalist"
