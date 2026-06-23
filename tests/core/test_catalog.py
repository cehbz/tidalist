import pytest

from tidalist.core.catalog import Track


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


def test_track_carries_audio_quality_and_popularity():
    from tidalist.core.identifiers import TrackId
    t = Track(id=TrackId("1"), title="Glad", artists=("Traffic",),
              audio_quality="HI_RES_LOSSLESS", popularity=72)
    assert t.audio_quality == "HI_RES_LOSSLESS"
    assert t.popularity == 72


def test_track_audio_quality_and_popularity_default_none():
    from tidalist.core.identifiers import TrackId
    t = Track(id=TrackId("1"), title="Glad", artists=("Traffic",))
    assert t.audio_quality is None and t.popularity is None
