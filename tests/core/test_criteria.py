from tidalist.core.recording import Performance, Credit, Recording
from tidalist.core.criteria import Verdict, PerformedBy, Studio


def _rec(performance=Performance.STUDIO, artist="Steve Winwood"):
    return Recording(artist=artist, title="Glad", performance=performance,
                     credits=(Credit(artist, "performer"),), first_released=1970)


def test_verdict_ok_has_no_violations():
    v = Verdict.ok()
    assert v.admitted is True and v.violations == ()


def test_verdict_rejected_collects_reasons():
    v = Verdict.rejected("live recording", "compilation")
    assert v.admitted is False and v.violations == ("live recording", "compilation")


def test_performed_by_passes_when_artist_performs():
    assert PerformedBy("Steve Winwood").violation(_rec()) is None


def test_performed_by_flags_a_cover():
    msg = PerformedBy("Steve Winwood").violation(_rec(artist="Joe Cocker"))
    assert msg is not None and "cover" in msg


def test_studio_flags_a_live_recording():
    assert Studio().violation(_rec(performance=Performance.LIVE)) == "live recording"


def test_studio_passes_a_studio_recording():
    assert Studio().violation(_rec()) is None
