from tidalist.core.recording import Candidate, Performance
from tidalist.metadata.musicbrainz import recording_from_musicbrainz, MusicBrainzMetadata


def _rec(disambiguation="", isrcs=("GBABC1234567",), dates=("1970-07-01", "1985-01-01"),
         length="386000"):
    return {
        "id": "rec-1",
        "title": "Glad",
        "length": length,
        "artist-credit": [{"artist": {"name": "Traffic"}}, " feat. ",
                          {"artist": {"name": "Steve Winwood"}}],
        "artist-credit-phrase": "Traffic feat. Steve Winwood",
        "isrc-list": list(isrcs),
        "release-list": [{"id": f"r{i}", "title": "John Barleycorn Must Die", "date": d}
                         for i, d in enumerate(dates)],
        "artist-relation-list": [{"type": "keyboard", "artist": {"name": "Steve Winwood"}}],
        "disambiguation": disambiguation,
    }


# A search hit is lighter than a full recording: no isrc-list, no artist-relation-list.
def _hit(id="rec-1", title="Glad", disambiguation=""):
    return {
        "id": id,
        "title": title,
        "length": "386000",
        "artist-credit": [{"artist": {"name": "Traffic"}}],
        "artist-credit-phrase": "Traffic",
        "release-list": [{"id": "r0", "title": "John Barleycorn Must Die", "date": "1970-07-01"}],
        "disambiguation": disambiguation,
    }


# --- recording_from_musicbrainz ---

def test_mbid_from_recording_id():
    assert recording_from_musicbrainz(_rec()).mbid == "rec-1"


def test_title_mapped():
    assert recording_from_musicbrainz(_rec()).title == "Glad"


def test_artist_from_credit_phrase():
    assert recording_from_musicbrainz(_rec()).artist == "Traffic feat. Steve Winwood"


def test_album_from_first_release_title():
    assert recording_from_musicbrainz(_rec()).album == "John Barleycorn Must Die"


def test_duration_from_length_milliseconds():
    assert recording_from_musicbrainz(_rec(length="386000")).duration_s == 386


def test_duration_none_when_length_absent():
    assert recording_from_musicbrainz(_rec(length=None)).duration_s is None


def test_isrc_is_first_in_list():
    assert recording_from_musicbrainz(_rec()).isrc == "GBABC1234567"


def test_isrc_none_when_absent():
    assert recording_from_musicbrainz(_rec(isrcs=())).isrc is None


def test_artist_credit_becomes_performer_credits_filtering_join_phrases():
    rec = recording_from_musicbrainz(_rec())
    performers = [c.artist for c in rec.credits if c.role == "performer"]
    assert "Traffic" in performers and "Steve Winwood" in performers


def test_relations_add_credits_with_their_role():
    rec = recording_from_musicbrainz(_rec())
    assert any(c.role == "keyboard" and c.artist == "Steve Winwood" for c in rec.credits)


def test_first_released_is_earliest_release_year():
    assert recording_from_musicbrainz(_rec(dates=("1985-01-01", "1970-07-01"))).first_released == 1970


def test_live_disambiguation_sets_performance_live():
    assert recording_from_musicbrainz(_rec(disambiguation="live, 1973")).performance is Performance.LIVE


def test_studio_default_is_unknown():
    assert recording_from_musicbrainz(_rec()).performance is Performance.UNKNOWN


# --- MusicBrainzMetadata.recordings_for ---

class _FakeMB:
    def __init__(self, search_list):
        self._search = search_list
        self.calls = []

    def search_recordings(self, query="", limit=None, **fields):
        self.calls.append(("search", fields, limit))
        return {"recording-list": self._search}

    def get_recording_by_id(self, id, includes=None, **kw):
        self.calls.append(("get", id, tuple(includes or [])))
        return {"recording": {}}


def test_recordings_for_maps_every_hit_in_order_without_selecting():
    mb = _FakeMB([_hit(id="a", title="Glad"),
                  _hit(id="b", title="Glad", disambiguation="live")])
    recs = MusicBrainzMetadata(mb).recordings_for(Candidate("Traffic", "Glad"))
    assert [r.mbid for r in recs] == ["a", "b"]
    assert recs[1].performance is Performance.LIVE


def test_recordings_for_is_discovery_only_no_full_fetch():
    mb = _FakeMB([_hit()])
    recs = MusicBrainzMetadata(mb).recordings_for(Candidate("Traffic", "Glad"))
    assert recs[0].isrc is None                        # ISRC is fetched lazily, not at discovery
    assert [c[0] for c in mb.calls] == ["search"]      # never calls get_recording_by_id


def test_recordings_for_searches_by_artist_and_title():
    mb = _FakeMB([_hit()])
    MusicBrainzMetadata(mb).recordings_for(Candidate("Traffic", "Glad"))
    assert mb.calls[0][1] == {"artist": "Traffic", "recording": "Glad"}


def test_recordings_for_empty_when_no_hits():
    assert MusicBrainzMetadata(_FakeMB([])).recordings_for(Candidate("X", "Y")) == []
