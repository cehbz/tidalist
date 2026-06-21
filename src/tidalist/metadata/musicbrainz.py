"""Map MusicBrainz recordings to core Recordings, and serve them through MetadataProvider.

MusicBrainz is recording-centric: it yields ISRC, performer relationships, and the
earliest release year. Callers must musicbrainzngs.set_useragent(...) before live use.
"""

import musicbrainzngs

from ..core.identifiers import ISRC
from ..core.recording import Candidate, Credit, Recording, Performance


def recording_from_musicbrainz(rec: dict) -> Recording:
    return Recording(
        isrc=_first_isrc(rec),
        performance=_performance(rec),
        credits=_credits(rec),
        first_released=_first_year(rec),
    )


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

    _INCLUDES = ["artists", "isrcs", "artist-rels", "releases"]

    def __init__(self, mb=musicbrainzngs):
        self._mb = mb

    def recording_for(self, candidate: Candidate) -> Recording | None:
        results = self._mb.search_recordings(
            artist=candidate.artist, recording=candidate.title, limit=1)
        hits = results.get("recording-list") or []
        if not hits:
            return None
        full = self._mb.get_recording_by_id(hits[0]["id"], includes=self._INCLUDES)
        return recording_from_musicbrainz(full["recording"])
