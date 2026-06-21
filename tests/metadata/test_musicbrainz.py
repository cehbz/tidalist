from tidalist.core.recording import Candidate, Performance
from tidalist.metadata.musicbrainz import recording_from_musicbrainz, MusicBrainzMetadata


def _rec(disambiguation="", isrcs=("GBABC1234567",), dates=("1970-07-01", "1985-01-01")):
    return {
        "id": "rec-1",
        "title": "Glad",
        "artist-credit": [{"artist": {"name": "Traffic"}}, " feat. ",
                          {"artist": {"name": "Steve Winwood"}}],
        "artist-credit-phrase": "Traffic feat. Steve Winwood",
        "isrc-list": list(isrcs),
        "release-list": [{"id": f"r{i}", "date": d} for i, d in enumerate(dates)],
        "artist-relation-list": [{"type": "keyboard", "artist": {"name": "Steve Winwood"}}],
        "disambiguation": disambiguation,
    }


# --- recording_from_musicbrainz ---

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


# --- MusicBrainzMetadata.recording_for ---

class _FakeMB:
    def __init__(self, search_list, full=None):
        self._search = search_list
        self._full = full
        self.calls = []

    def search_recordings(self, query="", limit=None, **fields):
        self.calls.append(("search", fields, limit))
        return {"recording-list": self._search}

    def get_recording_by_id(self, id, includes=None, **kw):
        self.calls.append(("get", id, tuple(includes or [])))
        return {"recording": self._full}


def test_recording_for_searches_then_fetches_and_maps():
    mb = _FakeMB([{"id": "rec-1"}], full=_rec())
    rec = MusicBrainzMetadata(mb).recording_for(Candidate("Traffic", "Glad"))
    assert rec.isrc == "GBABC1234567"
    assert rec.first_released == 1970
    assert mb.calls[0] == ("search", {"artist": "Traffic", "recording": "Glad"}, 1)
    assert mb.calls[1][1] == "rec-1"


def test_recording_for_none_when_no_search_hits():
    assert MusicBrainzMetadata(_FakeMB([])).recording_for(Candidate("X", "Y")) is None
