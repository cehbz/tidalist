import pytest

from tidalist.core.identifiers import ISRC, MBID
from tidalist.core.album import Album, TrackRef


def test_album_carries_identity_fields():
    a = Album(artist="Traffic", title="John Barleycorn Must Die",
              mbid=MBID("rg-1"), first_released=1970)
    assert a.artist == "Traffic" and a.title == "John Barleycorn Must Die"
    assert a.mbid == "rg-1" and a.first_released == 1970


def test_album_optional_fields_default_none():
    a = Album(artist="Blind Faith", title="Blind Faith")
    assert a.mbid is None and a.first_released is None


# --- Phase 4 Task 1: edition type fields ---

def test_album_carries_primary_type():
    a = Album(artist="Traffic", title="John Barleycorn Must Die", primary_type="Album")
    assert a.primary_type == "Album"


def test_album_primary_type_defaults_none():
    a = Album(artist="Traffic", title="John Barleycorn Must Die")
    assert a.primary_type is None


def test_album_carries_secondary_types():
    a = Album(artist="Traffic", title="Live Traffic", secondary_types=("Live",))
    assert a.secondary_types == ("Live",)


def test_album_secondary_types_defaults_empty_tuple():
    a = Album(artist="Traffic", title="John Barleycorn Must Die")
    assert a.secondary_types == ()


# --- Phase 2 (edition-distance): TrackRef and Album.tracklist ---

def test_trackref_constructs_and_compares_by_value():
    t1 = TrackRef(position=1, title="Glad", isrc=ISRC("GBABC1234567"),
                  mbid=MBID("rec-1"), duration_s=386)
    t2 = TrackRef(position=1, title="Glad", isrc=ISRC("GBABC1234567"),
                  mbid=MBID("rec-1"), duration_s=386)
    assert t1 == t2


def test_trackref_optional_fields_default_none():
    t = TrackRef(position=2, title="Freedom Rider")
    assert t.isrc is None
    assert t.mbid is None
    assert t.duration_s is None


def test_trackref_is_frozen():
    t = TrackRef(position=1, title="Glad")
    with pytest.raises((AttributeError, TypeError)):
        t.title = "Nope"  # type: ignore[misc]


def test_album_with_tracklist_holds_it():
    tracks = (
        TrackRef(position=1, title="Glad", isrc=ISRC("GBABC1234567"), duration_s=386),
        TrackRef(position=2, title="Freedom Rider"),
    )
    a = Album(artist="Traffic", title="John Barleycorn Must Die", tracklist=tracks)
    assert a.tracklist == tracks


def test_album_tracklist_defaults_empty_tuple():
    a = Album(artist="Traffic", title="John Barleycorn Must Die")
    assert a.tracklist == ()
