from tidalist.core.recording import Performance, Credit, Recording
from tidalist.core.ranking import PreferStudioEarliest


def _rec(performance, year):
    return Recording(artist="Steve Winwood", title="Glad", performance=performance,
                     credits=(Credit("Steve Winwood", "performer"),), first_released=year)


def test_recording_ranking_prefers_studio_over_live():
    r = PreferStudioEarliest()
    assert r.key(_rec(Performance.STUDIO, 1975)) < r.key(_rec(Performance.LIVE, 1970))


def test_recording_ranking_prefers_earliest_among_studio():
    r = PreferStudioEarliest()
    assert r.key(_rec(Performance.STUDIO, 1970)) < r.key(_rec(Performance.STUDIO, 1985))


def test_recording_ranking_sorts_unknown_year_last():
    r = PreferStudioEarliest()
    assert r.key(_rec(Performance.STUDIO, 1970)) < r.key(_rec(Performance.STUDIO, None))
