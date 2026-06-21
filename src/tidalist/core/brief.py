"""The Brief: a playlist's policy — its hard admissibility criteria.

Criteria are composable named rules; the Brief holds and applies them. Ordering is
not the Brief's concern: the golden Curator owns the recording-ranking.
"""

from dataclasses import dataclass

from .recording import Recording
from .criteria import Criterion, Verdict


@dataclass(frozen=True, slots=True)
class Brief:
    name: str
    criteria: tuple[Criterion, ...] = ()

    def judge(self, recording: Recording) -> Verdict:
        violations = tuple(
            reason for reason in (c.violation(recording) for c in self.criteria)
            if reason is not None
        )
        return Verdict.rejected(*violations) if violations else Verdict.ok()
