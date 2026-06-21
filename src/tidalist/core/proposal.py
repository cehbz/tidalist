"""A Proposal: one candidate after resolution — the unit reviewed."""

from dataclasses import dataclass

from .recording import Candidate, Recording
from .catalog import Track
from .criteria import Verdict
from .provenance import Provenance  # re-exported: legacy import site `from .proposal import Provenance`

__all__ = ["Provenance", "Proposal"]


@dataclass(frozen=True, slots=True)
class Proposal:
    candidate: Candidate
    track: Track | None
    recording: Recording | None
    verdict: Verdict
    provenance: Provenance

    @property
    def admissible(self) -> bool:
        return self.track is not None and self.verdict.admitted
