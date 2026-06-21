from datetime import datetime
from types import SimpleNamespace

from tidalist.core.identifiers import ISRC
from tidalist.tidal.catalog import track_from_tidal


def _artist(name):
    return SimpleNamespace(name=name)


def _tidal_track(**kw):
    base = dict(id=12345, name="Glad", artists=[_artist("Traffic")], isrc=None,
                album=SimpleNamespace(name="John Barleycorn Must Die", year=1970),
                tidal_release_date=datetime(1970, 7, 1), duration=421)
    return SimpleNamespace(**{**base, **kw})


def test_maps_core_fields():
    t = _tidal_track(artists=[_artist("Traffic"), _artist("Steve Winwood")],
                     isrc="GBABC1234567")
    track = track_from_tidal(t)
    assert track.id == "12345"
    assert track.title == "Glad"
    assert track.artists == ("Traffic", "Steve Winwood")
    assert track.isrc == ISRC("GBABC1234567")
    assert track.album == "John Barleycorn Must Die"
    assert track.duration_s == 421


def test_year_is_int_from_album_year():
    track = track_from_tidal(_tidal_track())
    assert track.year == 1970
    assert isinstance(track.year, int)


def test_year_falls_back_to_release_datetime_without_crashing():
    # Regression: tidalapi release dates are datetime; core Track demands int.
    t = _tidal_track(album=SimpleNamespace(name="A", year=None),
                     tidal_release_date=datetime(1973, 3, 1))
    assert track_from_tidal(t).year == 1973


def test_missing_isrc_and_dates_are_none():
    t = _tidal_track(isrc=None, album=None, tidal_release_date=None)
    track = track_from_tidal(t)
    assert track.isrc is None
    assert track.year is None


def test_single_artist_fallback():
    t = _tidal_track(artists=None, artist=_artist("Traffic"))
    assert track_from_tidal(t).artists == ("Traffic",)
