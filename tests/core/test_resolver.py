from tidalist.core.recording import Candidate, Performance, Credit, Recording
from tidalist.core.catalog import Edition, Track
from tidalist.core.identifiers import ISRC
from tidalist.core.criteria import PerformedBy
from tidalist.core.ranking import PreferOriginal
from tidalist.core.brief import Brief
from tidalist.core.proposal import Provenance
from tidalist.core.resolve import Resolver
from tests.fakes import FakeCatalog, FakeMetadataProvider

WINWOOD = (Credit("Steve Winwood", "performer"),)


def _brief(*criteria):
    return Brief("p", tuple(criteria), PreferOriginal())


def _resolve(resolver, candidate, brief):
    return resolver.resolve(candidate, brief, Provenance("nl"))


def test_resolves_by_isrc_when_present():
    hit = Track(id="9", title="Glad", artists=("Traffic",), isrc=ISRC("ZZ"))
    decoy = Track(id="1", title="Glad", artists=("Traffic",))
    p = _resolve(Resolver(FakeCatalog([decoy, hit])),
                 Candidate("Traffic", "Glad", isrc=ISRC("ZZ")), _brief())
    assert p.track is hit


def test_rejects_a_cover_when_required_performer_absent():
    track = Track(id="1", title="Feelin Alright", artists=("Joe Cocker",))
    recs = {"Feelin Alright": Recording(artist="Joe Cocker", title="Feelin Alright",
                                        performance=Performance.STUDIO,
                                        credits=(Credit("Joe Cocker", "performer"),),
                                        first_released=1969)}
    resolver = Resolver(FakeCatalog([track]), FakeMetadataProvider(recs))
    p = _resolve(resolver, Candidate("Joe Cocker", "Feelin Alright"),
                 _brief(PerformedBy("Steve Winwood")))
    assert p.track is track            # we found it...
    assert not p.admissible            # ...but it's a cover
    assert any("cover" in v for v in p.verdict.violations)


def test_prefers_original_edition_among_search_hits():
    original = Track(id="O", title="Glad", artists=("Traffic",),
                     album="John Barleycorn Must Die", edition=Edition.ORIGINAL, year=1970)
    comp = Track(id="C", title="Glad", artists=("Traffic",),
                 album="Gold", edition=Edition.COMPILATION, year=2005)
    recs = {"Glad": Recording(artist="Traffic", title="Glad", performance=Performance.STUDIO,
                              credits=WINWOOD, first_released=1970)}
    resolver = Resolver(FakeCatalog([comp, original]), FakeMetadataProvider(recs))
    p = _resolve(resolver, Candidate("Traffic", "Glad"), _brief(PerformedBy("Steve Winwood")))
    assert p.track.id == "O" and p.admissible


def test_pinned_album_beats_ranking():
    # The iconic live "Layla" the agent pinned must win over the higher-ranked studio cut.
    studio = Track(id="S", title="Layla", artists=("Eric Clapton",),
                   album="Layla and Other Assorted Love Songs",
                   edition=Edition.ORIGINAL, year=1970)
    unplugged = Track(id="U", title="Layla", artists=("Eric Clapton",),
                      album="Unplugged", edition=Edition.LIVE, year=1992)
    resolver = Resolver(FakeCatalog([studio, unplugged]))
    p = _resolve(resolver, Candidate("Eric Clapton", "Layla", album="Unplugged"), _brief())
    assert p.track.id == "U"


def test_no_catalog_match_is_rejected():
    p = _resolve(Resolver(FakeCatalog([])), Candidate("Nobody", "Nothing"), _brief())
    assert p.track is None
    assert not p.admissible
    assert "no catalog match" in p.verdict.violations
