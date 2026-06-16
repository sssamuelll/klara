from klara.curriculum.axes import LANGUAGE_AXES, axes_for


def test_german_declares_grammatical_axes_but_only_lexical_is_active_now():
    # El espacio de competencia del alemán está DECLARADO (compromiso de forma),
    # aunque v1 solo pueble el léxico.
    assert "lexical" in LANGUAGE_AXES["de"]
    assert "gender" in LANGUAGE_AXES["de"]


def test_every_supported_language_has_at_least_lexical():
    for code in ("de", "en", "fr", "ja", "pt", "es"):
        assert axes_for(code)[0] == "lexical"
