from tidalist.core.fidelity import Compromise


def test_compromise_carries_facet_desired_used_note():
    c = Compromise(facet="edition", desired="steven wilson",
                   used="(no preferred edition)", note="preferred edition unavailable")
    assert c.facet == "edition"
    assert c.desired == "steven wilson"
    assert c.used == "(no preferred edition)"
    assert "unavailable" in c.note
