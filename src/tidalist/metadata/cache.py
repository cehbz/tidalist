"""A persistent, transparent read-through cache around a musicbrainzngs client.

Wraps any object exposing the musicbrainzngs read methods and memoizes each call to disk,
keyed by a hash of (method, args, kwargs). It is a checkpoint/backstop for the slow
1-req/s curate: every response is persisted the instant it returns, so a crashed or re-run
curate replays from disk and fetches only what is genuinely new, and a query that recurs
across picks (a performer on several albums) hits the network once.

Read-through, write-on-miss, atomic per-entry writes. Only the documented read methods are
cached; every other attribute (e.g. ``set_useragent``) delegates straight through. Responses
are plain JSON-serialisable dicts/lists, so the store is a directory of inspectable JSON
files: ``<cache_dir>/<method>/<sha256>.json``.
"""

import hashlib
import json
from pathlib import Path

CACHED_METHODS = frozenset({
    "search_artists",
    "search_recordings",
    "search_release_groups",
    "browse_releases",
    "get_recording_by_id",
})


class CachingMusicBrainz:
    """Decorator over a musicbrainzngs-like client adding a persistent on-disk cache."""

    def __init__(self, mb, cache_dir):
        self._mb = mb
        self._dir = Path(cache_dir)

    def __getattr__(self, name):
        # _mb/_dir are real instance attributes; guarding avoids recursion if absent.
        if name in ("_mb", "_dir"):
            raise AttributeError(name)
        attr = getattr(self._mb, name)
        if name not in CACHED_METHODS or not callable(attr):
            return attr

        def cached(*args, **kwargs):
            return self._through(name, attr, args, kwargs)

        return cached

    def _through(self, method, fn, args, kwargs):
        path = self._entry_path(method, args, kwargs)
        if path.exists():
            return json.loads(path.read_text())
        result = fn(*args, **kwargs)
        self._store(path, result)
        return result

    def _store(self, path: Path, result) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(result, ensure_ascii=False))
        tmp.replace(path)  # atomic on POSIX; never leaves a half-written entry

    def _entry_path(self, method: str, args, kwargs) -> Path:
        key = json.dumps([method, args, kwargs], sort_keys=True,
                         ensure_ascii=False, default=str)
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self._dir / method / f"{digest}.json"
