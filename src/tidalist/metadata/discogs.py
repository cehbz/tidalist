"""Map discogs_client results to core Recordings, and serve them through MetadataProvider.

Discogs is release-centric: it yields a coarse Recording (year, live-or-not, release
artists as performers). It does not expose ISRC, so isrc stays None.
"""

from ..core.recording import Candidate, Credit, Recording, Performance


def recording_from_discogs(result) -> Recording:
    return Recording(
        isrc=None,
        performance=_performance(result),
        credits=tuple(Credit(a.name, "performer")
                      for a in getattr(result, "artists", None) or []),
        first_released=_year(result),
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

    def __init__(self, client):
        self._client = client

    def recording_for(self, candidate: Candidate) -> Recording | None:
        query = f"{candidate.artist} {candidate.title}"
        for result in self._client.search(query, type="release"):
            return recording_from_discogs(result)
        return None
