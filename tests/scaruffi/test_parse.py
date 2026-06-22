from tidalist.core.recording import Candidate, Kind
from tidalist.scaruffi.parse import parse_scaruffi


def _page(*lines):
    body = "\n".join(f"        <br>{line}" for line in lines)
    return f"<table><tr><td>\n{body}\n    </td></tr></table>"


def _one(*lines):
    candidates, provenances, _ = parse_scaruffi(_page(*lines))
    return candidates[0], provenances[0]


def test_basic_entry_maps_performer_work_and_year():
    cand, prov = _one("Bach: Brandenburg Concertos",
                      "Recommended recording: Il Giardino Armonico (1997)")
    assert cand == Candidate("Il Giardino Armonico", "Bach: Brandenburg Concertos",
                             year=1997, kind=Kind.ALBUM)
    assert prov.source == "scaruffi"


def test_year_range_uses_first_year():
    cand, _ = _one("Haydn: String Quartets",
                   "Recommended recording: Amadeus String Quartet (1963-73)")
    assert cand.year == 1963


def test_label_in_parens_is_not_a_year():
    cand, _ = _one("Bach: Organ Works",
                   "Recommended recording: Masaaki Suzuki (BIS)")
    assert cand.artist == "Masaaki Suzuki" and cand.year is None


def test_conductor_and_orchestra_kept_as_one_artist():
    cand, _ = _one("Beethoven: The Nine Symphonies",
                   "Recommended recording: Karajan & Berliner Philharmoniker  (1975-77)")
    assert cand.artist == "Karajan & Berliner Philharmoniker" and cand.year == 1975


def test_performer_only_has_no_year():
    cand, _ = _one("Beethoven: Sonatas",
                   "Recommended recording: Sviatoslav Richter")
    assert cand.artist == "Sviatoslav Richter" and cand.year is None


def test_also_clause_primary_is_the_candidate_alternates_go_to_provenance():
    cand, prov = _one(
        "Bach: Brandenburg Concertos",
        "Recommended recording: Il Giardino Armonico (1997) (also Trevor Pinnock and European Brandenburg Ensemble)")
    assert cand.artist == "Il Giardino Armonico"
    assert "Trevor Pinnock" in prov.note


def test_multiple_alternates_with_on_label():
    cand, prov = _one(
        "Bach: Goldberg Variations",
        "Recommended recording: Glenn Gould  (1955) (also Andras Schiff on ECM, Murray Perahia on Sony)")
    assert cand.artist == "Glenn Gould" and cand.year == 1955
    assert "Andras Schiff" in prov.note and "Murray Perahia" in prov.note


def test_or_separated_performers_primary_then_alternate():
    cand, prov = _one("Schubert: Piano Sonata D959",
                      "Recommended recording: Pollini or Krystian Zimerman")
    assert cand.artist == "Pollini"
    assert "Krystian Zimerman" in prov.note


def test_classical_work_is_album_kind_with_alternates_as_edition_context():
    # A whole-work recommendation is an album-kind golden unit. Its identity carries
    # only the primary performer + original year; the alternate recordings are
    # alternate *editions* of the same work and ride in provenance, never in identity.
    cand, prov = _one(
        "Beethoven: Symphony No. 9",
        "Recommended recording: Karajan (1962) (also Bernstein, Solti)")
    assert cand.kind is Kind.ALBUM
    assert cand.artist == "Karajan" and cand.year == 1962
    assert "Karajan" in prov.note
    assert "Bernstein" in prov.note and "Solti" in prov.note


def test_multiple_entries_yield_multiple_candidates_in_order():
    candidates, provenances, _ = parse_scaruffi(_page(
        "Bach: Brandenburg Concertos",
        "Recommended recording: Il Giardino Armonico (1997)",
        "",
        "Mozart: Requiem",
        "Recommended recording: Gardiner (1986)"))
    assert [c.title for c in candidates] == ["Bach: Brandenburg Concertos", "Mozart: Requiem"]
    assert len(provenances) == 2


def test_brief_is_named_with_no_hard_criteria():
    _, _, brief = parse_scaruffi(_page("Bach: x", "Recommended recording: Y (1997)"),
                                 name="Scaruffi Picks")
    assert brief.name == "Scaruffi Picks"
    assert brief.criteria == ()


def test_empty_or_tableless_html_yields_nothing():
    assert parse_scaruffi("<p>no table here</p>")[0] == []
