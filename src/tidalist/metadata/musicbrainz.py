"""Map MusicBrainz recordings to core Recordings, and serve them through MetadataProvider.

MusicBrainz is recording-centric: it yields the recording MBID, title, performer
relationships, and the earliest release year. `recordings_for` discovers candidates
from a search; it does not select among them (the Curator does) and does not pay for
the per-recording ISRC fetch — ISRC is enriched lazily once a recording is chosen.
Callers must musicbrainzngs.set_useragent(...) before live use.
"""

import musicbrainzngs

from ..core.identifiers import ISRC, MBID
from ..core.recording import Candidate, Credit, Recording, Performance


def recording_from_musicbrainz(rec: dict) -> Recording:
    """Map a MusicBrainz recording dict (search hit or full fetch) to a Recording.

    Tolerant of both shapes: a search hit omits isrc-list/artist-relation-list, so
    those map to None/empty until a full fetch enriches them.
    """
    return Recording(
        artist=rec.get("artist-credit-phrase") or _first_artist(rec),
        title=rec.get("title") or "",
        mbid=MBID(rec["id"]) if rec.get("id") else None,
        isrc=_first_isrc(rec),
        album=_first_album(rec),
        first_released=_first_year(rec),
        duration_s=_duration_s(rec),
        performance=_performance(rec),
        credits=_credits(rec),
    )


def _first_artist(rec: dict) -> str:
    for e in rec.get("artist-credit") or []:
        if isinstance(e, dict) and "artist" in e:
            return e["artist"].get("name", "")
    return ""


def _first_album(rec: dict) -> str | None:
    for r in rec.get("release-list") or []:
        if r.get("title"):
            return r["title"]
    return None


def _duration_s(rec: dict) -> int | None:
    length = rec.get("length")
    return int(length) // 1000 if length is not None and str(length).isdigit() else None


def _first_isrc(rec: dict) -> ISRC | None:
    isrcs = rec.get("isrc-list") or []
    return ISRC(isrcs[0]) if isrcs else None


def _performance(rec: dict) -> Performance:
    return (Performance.LIVE if "live" in (rec.get("disambiguation") or "").lower()
            else Performance.UNKNOWN)


def _credits(rec: dict) -> tuple[Credit, ...]:
    credits = [Credit(e["artist"]["name"], "performer")
               for e in rec.get("artist-credit") or []
               if isinstance(e, dict) and "artist" in e]
    for rel in rec.get("artist-relation-list") or []:
        name = (rel.get("artist") or {}).get("name")
        if name:
            credits.append(Credit(name, rel.get("type", "performer")))
    return tuple(credits)


def _first_year(rec: dict) -> int | None:
    years = [int(d[:4]) for r in rec.get("release-list") or []
             if (d := r.get("date")) and d[:4].isdigit()]
    frd = rec.get("first-release-date")
    if frd and frd[:4].isdigit():
        years.append(int(frd[:4]))
    return min(years) if years else None


class MusicBrainzMetadata:
    """MetadataProvider port backed by musicbrainzngs."""

    def __init__(self, mb=musicbrainzngs, *, limit: int = 25):
        self._mb = mb
        self._limit = limit

    def recordings_for(self, candidate: Candidate) -> list[Recording]:
        results = self._mb.search_recordings(
            artist=candidate.artist, recording=candidate.title, limit=self._limit)
        return [recording_from_musicbrainz(h) for h in results.get("recording-list") or []]
