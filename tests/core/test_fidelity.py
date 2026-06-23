from tidalist.core.fidelity import Compromise, PlatformCandidate
from tidalist.core.recording import Performance


def test_compromise_carries_facet_desired_used_note():
    c = Compromise(facet="edition", desired="steven wilson",
                   used="(no preferred edition)", note="preferred edition unavailable")
    assert c.facet == "edition"
    assert c.desired == "steven wilson"
    assert c.used == "(no preferred edition)"
    assert "unavailable" in c.note


def test_platform_candidate_defaults_are_observation_unknowns():
    c = PlatformCandidate(ref="A1", title="Mr. Fantasy")
    assert c.artists == () and c.isrc is None and c.year is None and c.tracks == ()
    assert c.release_class is None
    assert c.performance is Performance.UNKNOWN
    assert c.source_kind is None and c.audio_quality is None and c.popularity is None
