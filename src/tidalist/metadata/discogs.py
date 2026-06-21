"""Map discogs_client results to core Recordings, and serve them through MetadataProvider.

Discogs is release-centric: a search result is a release, not a recording, so it cannot
supply a track title or ISRC. The recording's title/artist come from the Candidate; the
release supplies edition-grade facts (album, year, live-or-not, release artists).
`recordings_for` discovers; it does not select.
"""

from ..core.recording import Candidate, Credit, Recording, Performance
from .rate_limit import MinInterval


def recording_from_discogs(result, candidate: Candidate) -> Recording:
    return Recording(
        artist=candidate.artist,
        title=candidate.title,
        isrc=None,
        album=getattr(result, "title", None) or None,
        first_released=_year(result),
        performance=_performance(result),
        credits=tuple(Credit(a.name, "performer")
                      for a in getattr(result, "artists", None) or []),
    )


def _performance(result) -> Performance:
    for fmt in getattr(result, "formats", None) or []:
        descriptions = fmt.get("descriptions") if isinstance(fmt, dict) else None
        if descriptions and any(d.lower() == "live" for d in descriptions):
            return Performance.LIVE
    return Performance.UNKNOWN


def _year(result) -> int | None:
    y = getattr(result, "year", None)
    if isinstance(y, bool):
        return None
    if isinstance(y, int):
        return y if y > 0 else None
    if isinstance(y, str) and y.strip().isdigit():
        n = int(y)
        return n if n > 0 else None
    return None


class DiscogsMetadata:
    """MetadataProvider port backed by a discogs_client.Client."""

    def __init__(self, client, *, limiter=None, rate_limit: int = 60):
        self._client = client
        self._limiter = limiter or MinInterval(rate_limit)

    def recordings_for(self, candidate: Candidate) -> list[Recording]:
        self._limiter.wait()
        query = f"{candidate.artist} {candidate.title}"
        return [recording_from_discogs(r, candidate)
                for r in self._client.search(query, type="release")]
