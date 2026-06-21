from types import SimpleNamespace

from tidalist.core.recording import Candidate, Performance
from tidalist.metadata.discogs import recording_from_discogs, DiscogsMetadata


def _result(artists=("Traffic",), formats=None, year=1970):
    return SimpleNamespace(
        artists=[SimpleNamespace(name=a) for a in artists],
        formats=formats if formats is not None else [{"name": "Vinyl", "descriptions": ["LP", "Album"]}],
        year=year,
    )


# --- recording_from_discogs ---

def test_maps_artists_to_performer_credits():
    rec = recording_from_discogs(_result(artists=("Traffic", "Steve Winwood")))
    assert [c.artist for c in rec.credits] == ["Traffic", "Steve Winwood"]
    assert all(c.role == "performer" for c in rec.credits)


def test_first_released_from_int_year():
    assert recording_from_discogs(_result(year=1970)).first_released == 1970


def test_first_released_from_string_year():
    assert recording_from_discogs(_result(year="1970")).first_released == 1970


def test_missing_year_is_none():
    assert recording_from_discogs(_result(year=0)).first_released is None


def test_live_format_sets_performance_live():
    r = _result(formats=[{"name": "CD", "descriptions": ["Album", "Live"]}])
    assert recording_from_discogs(r).performance is Performance.LIVE


def test_non_live_format_is_unknown_performance():
    assert recording_from_discogs(_result()).performance is Performance.UNKNOWN


def test_isrc_is_none():
    assert recording_from_discogs(_result()).isrc is None


# --- DiscogsMetadata.recording_for ---

class _FakeClient:
    def __init__(self, results):
        self._results = results
        self.queries = []

    def search(self, query, type=None):
        self.queries.append((query, type))
        return self._results


def test_recording_for_maps_first_result():
    client = _FakeClient([_result(year=1970), _result(year=2005)])
    rec = DiscogsMetadata(client).recording_for(Candidate("Traffic", "Glad"))
    assert rec.first_released == 1970
    assert client.queries == [("Traffic Glad", "release")]


def test_recording_for_none_when_no_results():
    assert DiscogsMetadata(_FakeClient([])).recording_for(Candidate("X", "Y")) is None


def test_recording_for_waits_on_the_limiter():
    calls = []

    class _Limiter:
        def wait(self):
            calls.append(1)

    DiscogsMetadata(_FakeClient([_result()]), limiter=_Limiter()).recording_for(
        Candidate("Traffic", "Glad"))
    assert calls == [1]
