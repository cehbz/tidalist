from tidalist.core.recording import Candidate
from tidalist.core.catalog import Track
from tidalist.core.criteria import Verdict
from tidalist.core.proposal import Proposal, Provenance


def _proposal(track, verdict):
    return Proposal(Candidate("a", "t"), track, None, verdict, Provenance("nl"))


def test_admissible_with_track_and_admitted_verdict():
    t = Track(id="1", title="t", artists=("a",))
    assert _proposal(t, Verdict.ok()).admissible is True


def test_not_admissible_without_a_track():
    assert _proposal(None, Verdict.ok()).admissible is False


def test_not_admissible_when_verdict_rejected():
    t = Track(id="1", title="t", artists=("a",))
    assert _proposal(t, Verdict.rejected("live recording")).admissible is False
