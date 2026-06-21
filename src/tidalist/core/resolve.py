"""Resolve a Candidate to a catalog Track, enrich, judge.

Track-selection precedence:
  1. ISRC          — exact recording.
  2. album/version — hits on the candidate's named album (the pin).
  3. ranking       — tiebreaker among equivalent hits.
"""

from .ports import Catalog, MetadataProvider
from .recording import Candidate, Recording, Performance, Credit
from .catalog import Track
from .brief import Brief
from .criteria import Verdict
from .proposal import Proposal, Provenance


class Resolver:
    def __init__(self, catalog: Catalog, metadata: MetadataProvider | None = None):
        self._catalog = catalog
        self._metadata = metadata

    def resolve(self, candidate: Candidate, brief: Brief, provenance: Provenance) -> Proposal:
        # Transitional: take the first discovered recording. The golden Curator (Phase B)
        # replaces this with brief-driven discrimination over the full recordings_for list.
        recordings = self._metadata.recordings_for(candidate) if self._metadata else []
        recording = recordings[0] if recordings else None
        track = self._find_track(candidate, brief, recording)
        if track is None:
            return Proposal(candidate, None, recording,
                            Verdict.rejected("no catalog match"), provenance)
        judged = recording if recording is not None else self._recording_from(track)
        return Proposal(candidate, track, recording, brief.judge(judged), provenance)

    def _find_track(self, candidate: Candidate, brief: Brief,
                    recording: Recording | None) -> Track | None:
        if candidate.isrc is not None:
            by_isrc = self._catalog.track_by_isrc(candidate.isrc)
            if by_isrc is not None:
                return by_isrc

        hits = self._catalog.search_tracks(candidate.search_query())
        if not hits:
            return None

        if candidate.album:
            wanted = candidate.album.casefold()
            pinned = [t for t in hits if t.album and wanted in t.album.casefold()]
            if pinned:
                hits = pinned

        return min(hits, key=lambda t: brief.rank_key(recording, t))

    @staticmethod
    def _recording_from(track: Track) -> Recording:
        """Fallback recording with no MetadataProvider: trust the track."""
        return Recording(
            artist=track.artists[0] if track.artists else "",
            title=track.title,
            isrc=track.isrc,
            album=track.album,
            first_released=track.year,
            duration_s=track.duration_s,
            performance=Performance.UNKNOWN,
            credits=tuple(Credit(a, "performer") for a in track.artists),
        )
