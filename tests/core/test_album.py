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
