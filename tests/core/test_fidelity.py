from dataclasses import dataclass as _dc

from tidalist.core.fidelity import (
    Compromise, PlatformCandidate, realize_distance, choose,
    IdentityFacet, W_IDENTITY, W_MARKER,
    EditionFacet, edition_distance,
)
from tidalist.core.edition import EditionPreference
from tidalist.core.identifiers import ISRC
from tidalist.core.recording import Performance, Recording
from tidalist.core.album import Album


@_dc
class _FixedFacet:
    name = "fixed"
    weight = 1.0
    table: dict          # ref -> distance
    note: str | None = None
    def distance(self, golden, cand): return self.table[cand.ref]
    def compromise(self, golden, cand):
        return Compromise("fixed", "x", "y", self.note) if self.note else None


def test_realize_distance_sums_weighted_facets():
    cand = PlatformCandidate(ref="A", title="t")
    g = Recording(artist="a", title="t")
    facets = [_FixedFacet(table={"A": 2.0}), _FixedFacet(table={"A": 3.0})]
    assert realize_distance(g, cand, facets) == 5.0


def test_choose_returns_min_distance_candidate_and_its_compromises():
    g = Recording(artist="a", title="t")
    c_near = PlatformCandidate(ref="near", title="t")
    c_far = PlatformCandidate(ref="far", title="t")
    facets = [_FixedFacet(table={"near": 1.0, "far": 9.0}, note="used a substitute")]
    chosen, comps = choose(g, [c_far, c_near], facets)
    assert chosen.ref == "near"
    assert len(comps) == 1 and comps[0].note == "used a substitute"


def test_choose_breaks_ties_deterministically_by_ref():
    g = Recording(artist="a", title="t")
    a = PlatformCandidate(ref="a", title="t")
    b = PlatformCandidate(ref="b", title="t")
    facets = [_FixedFacet(table={"a": 5.0, "b": 5.0})]
    # Equal distance → lexicographically smaller ref wins, regardless of input order.
    assert choose(g, [b, a], facets)[0].ref == "a"
    assert choose(g, [a, b], facets)[0].ref == "a"


def test_choose_empty_candidates_returns_none_and_no_compromises():
    g = Recording(artist="a", title="t")
    assert choose(g, [], [_FixedFacet(table={})]) == (None, ())


def test_compromise_carries_facet_desired_used_note():
    c = Compromise(facet="edition", desired="steven wilson",
                   used="(no preferred edition)", note="preferred edition unavailable")
    assert c.facet == "edition"
    assert c.desired == "steven wilson"
    assert c.used == "(no preferred edition)"
    assert "unavailable" in c.note


def test_platform_candidate_defaults_are_observation_unknowns():
    c = PlatformCandidate(ref="A1", title="Mr. Fantasy")
    assert c.artists == () and c.isrc is None and c.year is None and c.tracks == ()
    assert c.release_class is None
    assert c.performance is Performance.UNKNOWN
    assert c.source_kind is None and c.audio_quality is None and c.popularity is None


def test_identity_dominates_marker():
    assert W_IDENTITY > W_MARKER


def test_identity_recording_isrc_match_is_zero():
    g = Recording(artist="Traffic", title="Glad", isrc=ISRC("GB1"))
    cand = PlatformCandidate(ref="t1", title="Glad", isrc=ISRC("GB1"))
    assert IdentityFacet().distance(g, cand) == 0.0


def test_identity_recording_isrc_mismatch_is_w_identity():
    g = Recording(artist="Traffic", title="Glad", isrc=ISRC("GB1"))
    cand = PlatformCandidate(ref="t2", title="Glad", isrc=ISRC("GB2"))
    assert IdentityFacet().distance(g, cand) == W_IDENTITY


def test_identity_recording_unknown_isrc_is_zero():
    g = Recording(artist="Traffic", title="Glad")          # no isrc
    cand = PlatformCandidate(ref="t3", title="Glad", isrc=ISRC("GB9"))
    assert IdentityFacet().distance(g, cand) == 0.0


def test_identity_album_is_zero():
    g = Album(artist="Traffic", title="Mr. Fantasy")
    cand = PlatformCandidate(ref="A1", title="Mr. Fantasy")
    assert IdentityFacet().distance(g, cand) == 0.0
    assert IdentityFacet().compromise(g, cand) is None


# ---------------------------------------------------------------------------
# EditionFacet tests
# ---------------------------------------------------------------------------

def test_edition_facet_distance_matches_edition_distance_for_albums():
    g = Album(artist="Yes", title="Close to the Edge", first_released=1972)
    pref = EditionPreference(markers=(), prefer_original=True)
    cand = PlatformCandidate(ref="orig", title="Close to the Edge", year=1972)
    assert EditionFacet(pref).distance(g, cand) == edition_distance(g, cand, pref)


def test_edition_facet_no_op_on_recordings():
    g = Recording(artist="Yes", title="Roundabout")
    pref = EditionPreference(markers=("steven wilson",))
    cand = PlatformCandidate(ref="x", title="Roundabout")
    assert EditionFacet(pref).distance(g, cand) == 0.0
    assert EditionFacet(pref).compromise(g, cand) is None


def test_edition_facet_compromise_when_no_marker_present():
    g = Album(artist="Yes", title="Close to the Edge", first_released=1972)
    pref = EditionPreference(markers=("steven wilson",), prefer_original=True)
    cand = PlatformCandidate(ref="orig", title="Close to the Edge", year=1972)
    comp = EditionFacet(pref).compromise(g, cand)
    assert comp is not None
    assert comp.facet == "edition" and comp.desired == "steven wilson"
    assert comp.note == "preferred edition (steven wilson) unavailable"


def test_edition_facet_no_compromise_when_marker_present():
    g = Album(artist="Yes", title="Close to the Edge", first_released=1972)
    pref = EditionPreference(markers=("steven wilson",))
    cand = PlatformCandidate(ref="sw", title="Close to the Edge (Steven Wilson Mix)", year=2013)
    assert EditionFacet(pref).compromise(g, cand) is None
