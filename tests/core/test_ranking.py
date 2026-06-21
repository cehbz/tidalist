from tidalist.core.recording import Performance, Credit, Recording
from tidalist.core.catalog import Edition, Track
from tidalist.core.ranking import PreferOriginal


def _rec(performance, year):
    return Recording(None, performance, (Credit("Steve Winwood", "performer"),), year)


def _track(edition=Edition.ORIGINAL, year=1970):
    return Track(id="x", title="t", artists=("a",), edition=edition, year=year)


def test_studio_ranks_before_live():
    r = PreferOriginal()
    studio = r.key(_rec(Performance.STUDIO, 1970), _track(year=1970))
    live = r.key(_rec(Performance.LIVE, 1970), _track(year=1970))
    assert studio < live


def test_original_edition_ranks_before_compilation():
    r = PreferOriginal()
    original = r.key(_rec(Performance.STUDIO, 1970), _track(edition=Edition.ORIGINAL))
    comp = r.key(_rec(Performance.STUDIO, 1970), _track(edition=Edition.COMPILATION))
    assert original < comp


def test_original_edition_ranks_before_live_album():
    r = PreferOriginal()
    original = r.key(_rec(Performance.STUDIO, 1970), _track(edition=Edition.ORIGINAL))
    live = r.key(_rec(Performance.STUDIO, 1970), _track(edition=Edition.LIVE))
    assert original < live


def test_earlier_year_breaks_ties():
    r = PreferOriginal()
    early = r.key(_rec(Performance.STUDIO, 1970), _track(year=1970))
    late = r.key(_rec(Performance.STUDIO, 1990), _track(year=1990))
    assert early < late


def test_key_tolerates_missing_recording():
    r = PreferOriginal()
    k = r.key(None, _track(year=1970))
    assert isinstance(k, tuple)
