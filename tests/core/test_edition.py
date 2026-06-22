from tidalist.core.edition import EditionPreference, EditionPolicy


def test_edition_preference_defaults():
    p = EditionPreference()
    assert p.markers == () and p.prefer_original is True


def test_markers_stored_lowercased():
    p = EditionPreference(markers=("Steven Wilson", "Mobile Fidelity"))
    assert p.markers == ("steven wilson", "mobile fidelity")


def test_policy_default_prefers_steven_wilson_then_mofi():
    d = EditionPolicy.default()
    assert d.markers == ("steven wilson", "mobile fidelity")
    assert d.prefer_original is True
