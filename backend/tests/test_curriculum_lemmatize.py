"""El lematizador mapea flexiones alemanas a un lema canónico (minúsculas),
para que cobertura y known-set cuenten familias y no flexiones."""

import pytest

from klara.curriculum.lemmatize import canonical_lemma


@pytest.mark.parametrize(
    "surface,expected",
    [
        ("läuft", "laufen"),
        ("gelaufen", "laufen"),
        ("Häuser", "haus"),
        ("Tische", "tisch"),
        ("Haus", "haus"),
    ],
)
def test_german_inflections_map_to_lemma(surface, expected):
    assert canonical_lemma(surface, "de") == expected


def test_blank_and_unknown_are_safe():
    assert canonical_lemma("", "de") == ""
    # idioma no soportado → identidad en minúsculas, sin crash
    assert canonical_lemma("Casa", "xx") == "casa"
