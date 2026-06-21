"""The Brief: a playlist's policy — its hard criteria and its soft ranking.

Criteria are composable named rules, ranking is orthogonal, the Brief holds 
and applies them.
"""

from dataclasses import dataclass

from .recording import Recording
from .catalog import Track
from .criteria import Criterion, Verdict
from .ranking import Ranking


@dataclass(frozen=True, slots=True)
class Brief:
    name: str
    criteria: tuple[Criterion, ...]
    ranking: Ranking

    def judge(self, recording: Recording) -> Verdict:
        violations = tuple(
            reason for reason in (c.violation(recording) for c in self.criteria)
            if reason is not None
        )
        return Verdict.rejected(*violations) if violations else Verdict.ok()

    def rank_key(self, recording: Recording | None, track: Track) -> tuple:
        return self.ranking.key(recording, track)
