import pytest

from tidalist.core.recording import Candidate, Performance, Credit, Recording
from tidalist.core.catalog import Track
from tidalist.core.criteria import PerformedBy
from tidalist.core.ranking import PreferOriginal
from tidalist.core.brief import Brief
from tidalist.core.resolve import Resolver
from tidalist.core.curate import Curator, Publisher
from tidalist.core.errors import CatalogError
from tests.fakes import FakeCatalog, FakeMetadataProvider


def _brief(*criteria):
    return Brief("Winwood", tuple(criteria), PreferOriginal())


def test_draft_resolves_each_candidate_and_stamps_source():
    glad = Track(id="S", title="Glad", artists=("Traffic",))
    proposals = Curator(Resolver(FakeCatalog([glad]))).draft(
        _brief(), [Candidate("Traffic", "Glad")], source="nl")
    assert len(proposals) == 1
    assert proposals[0].track is glad
    assert proposals[0].provenance.source == "nl"


def test_publish_adds_only_admitted_deduped_and_ordered():
    glad = Track(id="S", title="Glad", artists=("Traffic",))
    cover = Track(id="C", title="Feelin Alright", artists=("Joe Cocker",))
    recs = {
        "Glad": Recording(None, Performance.STUDIO,
                          (Credit("Steve Winwood", "performer"),), 1970),
        "Feelin Alright": Recording(None, Performance.STUDIO,
                                    (Credit("Joe Cocker", "performer"),), 1969),
    }
    cat = FakeCatalog([glad, cover])
    proposals = Curator(Resolver(cat, FakeMetadataProvider(recs))).draft(
        _brief(PerformedBy("Steve Winwood")),
        [Candidate("Traffic", "Glad"),
         Candidate("Joe Cocker", "Feelin Alright"),   # cover -> rejected
         Candidate("Traffic", "Glad")],               # duplicate -> collapsed
        source="nl")
    pid = Publisher(cat).publish("Winwood", proposals)
    assert cat.playlists[pid] == ["S"]


def test_publish_raises_when_nothing_admissible():
    with pytest.raises(CatalogError):
        Publisher(FakeCatalog([])).publish("Empty", [])
