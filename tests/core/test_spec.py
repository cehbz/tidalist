import json

import pytest

from tidalist.core.identifiers import ISRC, MBID
from tidalist.core.recording import Candidate, Credit, Recording, Performance
from tidalist.core.catalog import Edition, Track
from tidalist.core.criteria import PerformedBy, Studio, Verdict
from tidalist.core.ranking import PreferOriginal
from tidalist.core.brief import Brief
from tidalist.core.proposal import Proposal, Provenance
from tidalist.core.spec import to_spec, from_spec


def _example():
    brief = Brief("Winwood", (PerformedBy("Steve Winwood"), Studio()), PreferOriginal())
    rec = Recording(artist="Traffic", title="Glad", mbid=MBID("rec-1"),
                    isrc=ISRC("GBABC1234567"), album="John Barleycorn Must Die",
                    first_released=1970, duration_s=386, performance=Performance.STUDIO,
                    credits=(Credit("Steve Winwood", "performer"),))
    track = Track(id="S", title="Glad", artists=("Traffic",), isrc=ISRC("GBABC1234567"),
                  album="John Barleycorn Must Die", year=1970, edition=Edition.ORIGINAL)
    proposals = [Proposal(
        Candidate("Traffic", "Glad", album="John Barleycorn Must Die", year=1970),
        track, rec, Verdict.ok(), Provenance("nl", "signature track"))]
    return brief, proposals


def test_round_trips_brief_and_proposals():
    brief, proposals = _example()
    brief2, proposals2 = from_spec(to_spec(brief, proposals))
    assert brief2 == brief
    assert proposals2 == proposals


def test_round_trips_an_unresolved_rejected_proposal():
    brief = Brief("x", (), PreferOriginal())
    p = Proposal(Candidate("a", "t"), None, None,
                 Verdict.rejected("no catalog match"), Provenance("nl"))
    _, proposals2 = from_spec(to_spec(brief, [p]))
    assert proposals2 == [p]


def test_spec_is_pure_json():
    brief, proposals = _example()
    spec = to_spec(brief, proposals)
    assert json.loads(json.dumps(spec)) == spec


def test_unknown_criterion_type_raises():
    bad = {"name": "x", "criteria": [{"type": "nope"}],
           "ranking": {"type": "prefer_original"}, "proposals": []}
    with pytest.raises(ValueError):
        from_spec(bad)
