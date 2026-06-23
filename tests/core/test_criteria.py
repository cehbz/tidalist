from tidalist.core.recording import Performance, Credit, Recording
from tidalist.core.album import Album, ReleaseTrait
from tidalist.core.criteria import Verdict, PerformedBy, Studio, NotCompilation, NotLive


def _rec(performance=Performance.STUDIO, artist="Steve Winwood"):
    return Recording(artist=artist, title="Glad", performance=performance,
                     credits=(Credit(artist, "performer"),), first_released=1970)


def _album(traits=frozenset()):
    return Album(artist="Traffic", title="John Barleycorn Must Die",
                 traits=traits)


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


# --- Phase 4 Task 1: recording criteria are no-ops on Albums ---

def test_performed_by_is_noop_on_album():
    assert PerformedBy("Traffic").violation(_album()) is None


def test_studio_is_noop_on_album():
    assert Studio().violation(_album()) is None


# --- NotCompilation ---

def test_not_compilation_passes_studio_album():
    assert NotCompilation().violation(_album()) is None


def test_not_compilation_flags_compilation_album():
    reason = NotCompilation().violation(_album(traits=frozenset({ReleaseTrait.COMPILATION})))
    assert reason == "compilation"


def test_not_compilation_is_noop_on_recording():
    assert NotCompilation().violation(_rec()) is None


# --- NotLive ---

def test_not_live_passes_studio_album():
    assert NotLive().violation(_album()) is None


def test_not_live_flags_live_album():
    reason = NotLive().violation(_album(traits=frozenset({ReleaseTrait.LIVE})))
    assert reason == "live album"


def test_not_live_is_noop_on_recording():
    assert NotLive().violation(_rec()) is None
