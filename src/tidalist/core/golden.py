"""The golden stage: candidates + metadata + a brief -> an ordered, platform-agnostic
playlist of recordings.

Providers discover recordings; the Curator discriminates. For each candidate it judges
the discovered recordings against the brief's criteria and chooses one by the
recording-ranking, preferring admissible takes. A candidate that finds nothing, or whose
takes all violate the brief, still yields an entry — with a rejected verdict — so the
result is reviewable; realization later acts only on admitted entries.
"""

from dataclasses import dataclass

from .ports import MetadataProvider
from .recording import Candidate, Recording
from .brief import Brief
from .criteria import Verdict
from .ranking import RecordingRanking, PreferStudioEarliest
from .provenance import Provenance


@dataclass(frozen=True, slots=True)
class GoldenEntry:
    recording: Recording
    provenance: Provenance
    verdict: Verdict


@dataclass(frozen=True, slots=True)
class GoldenPlaylist:
    name: str
    brief: Brief
    entries: tuple[GoldenEntry, ...]


class Curator:
    def __init__(self, metadata: MetadataProvider,
                 ranking: RecordingRanking = PreferStudioEarliest()):
        self._metadata = metadata
        self._ranking = ranking

    def curate(self, brief: Brief, candidates: list[Candidate],
               provenances: list[Provenance] | None = None) -> GoldenPlaylist:
        if provenances is None:
            provenances = [Provenance("nl")] * len(candidates)
        elif len(provenances) != len(candidates):
            raise ValueError("provenances must be one per candidate")
        entries = tuple(self._entry(brief, c, p) for c, p in zip(candidates, provenances))
        return GoldenPlaylist(brief.name, brief, entries)

    def _entry(self, brief: Brief, candidate: Candidate, provenance: Provenance) -> GoldenEntry:
        recordings = self._metadata.recordings_for(candidate)
        if not recordings:
            miss = Recording(artist=candidate.artist, title=candidate.title)
            return GoldenEntry(miss, provenance, Verdict.rejected("no recording found"))
        chosen = self._choose(brief, recordings)
        return GoldenEntry(chosen, provenance, brief.judge(chosen))

    def _choose(self, brief: Brief, recordings: list[Recording]) -> Recording:
        admissible = [r for r in recordings if brief.judge(r).admitted]
        return min(admissible or recordings, key=self._ranking.key)
