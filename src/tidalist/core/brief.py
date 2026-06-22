"""The Brief: a playlist's policy — its hard admissibility criteria.

Criteria are composable named rules; the Brief holds and applies them. Ordering is
not the Brief's concern: the golden Curator owns the recording-ranking.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .recording import Recording
from .criteria import Criterion, Verdict

if TYPE_CHECKING:
    from .album import Album


@dataclass(frozen=True, slots=True)
class Brief:
    name: str
    criteria: tuple[Criterion, ...] = ()

    def judge(self, item: Album | Recording) -> Verdict:
        violations = tuple(
            reason for reason in (c.violation(item) for c in self.criteria)
            if reason is not None
        )
        return Verdict.rejected(*violations) if violations else Verdict.ok()
