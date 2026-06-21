from tidalist.core.recording import Performance, Credit, Recording
from tidalist.core.catalog import Edition, Track
from tidalist.core.criteria import PerformedBy, Studio
from tidalist.core.ranking import PreferOriginal
from tidalist.core.brief import Brief


def _rec(performance=Performance.STUDIO, artist="Steve Winwood"):
    return Recording(artist=artist, title="Glad", performance=performance,
                     credits=(Credit(artist, "performer"),), first_released=1970)


def _brief(*criteria):
    return Brief("p", tuple(criteria), PreferOriginal())


def test_admits_when_all_criteria_pass():
    v = _brief(PerformedBy("Steve Winwood"), Studio()).judge(_rec())
    assert v.admitted and v.violations == ()


def test_rejects_and_accumulates_violations():
    v = _brief(PerformedBy("Steve Winwood"), Studio()).judge(
        _rec(performance=Performance.LIVE, artist="Joe Cocker"))
    assert not v.admitted
    assert len(v.violations) == 2


def test_no_criteria_admits_everything():
    assert _brief().judge(_rec(performance=Performance.LIVE)).admitted is True


def test_rank_key_delegates_to_ranking():
    brief = _brief()
    track = Track(id="1", title="t", artists=("a",), edition=Edition.ORIGINAL, year=1970)
    rec = _rec()
    assert brief.rank_key(rec, track) == PreferOriginal().key(rec, track)
