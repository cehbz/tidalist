from tidalist.core.identifiers import MBID
from tidalist.core.album import Album


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
