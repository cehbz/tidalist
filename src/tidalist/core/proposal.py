"""A Proposal: one candidate after resolution — the unit reviewed."""

from dataclasses import dataclass

from .recording import Candidate, Recording
from .catalog import Track
from .criteria import Verdict


@dataclass(frozen=True, slots=True)
class Provenance:
    source: str        # "scaruffi" | "nl"
    note: str = ""


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
