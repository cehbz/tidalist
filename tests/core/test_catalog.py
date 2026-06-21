import pytest

from tidalist.core.catalog import Edition, Track, Album


def test_primary_artist_is_first():
    t = Track(id="1", title="Glad", artists=("Traffic", "Steve Winwood"))
    assert t.primary_artist == "Traffic"


def test_track_year_must_be_int_not_datetime_string():
    # Structural guard against the legacy `TidalAlbum.year` datetime crash:
    # adapters must normalize to int at the boundary.
    with pytest.raises(TypeError):
        Track(id="1", title="Glad", artists=("Traffic",), year="1970")


def test_track_requires_at_least_one_artist():
    with pytest.raises(ValueError):
        Track(id="1", title="Glad", artists=())


def test_track_edition_defaults_to_unknown():
    t = Track(id="1", title="Glad", artists=("Traffic",))
    assert t.edition is Edition.UNKNOWN


def test_album_holds_metadata():
    a = Album(id="9", title="John Barleycorn Must Die", artists=("Traffic",), year=1970)
    assert a.year == 1970
