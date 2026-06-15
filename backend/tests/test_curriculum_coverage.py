"""verify_coverage devuelve el subconjunto de lemas que SÍ aparecen (lematizados)
en la historia. Lo no cubierto no se afirma enseñar (spec §8)."""

from klara.curriculum.coverage import verify_coverage


def _content(*targets_in_sentences: str) -> dict:
    return {
        "sentences": [
            {"target": s, "native": "", "new_words": [], "breakdown": []}
            for s in targets_in_sentences
        ]
    }


def test_covered_lemmas_match_inflected_forms():
    content = _content("Die Häuser sind groß.", "Er läuft schnell.")
    # Los objetivos llegan en su FORMA NATURAL de lema (como los guarda
    # VocabItem.lemma: sustantivo capitalizado). canonical_lemma necesita la
    # mayúscula del sustantivo alemán; pasar "haus" en minúsculas lo re-lematizaría
    # como verbo ("hausen") y nunca casaría — ver el contrato en lemmatize.py.
    covered = verify_coverage(content, ["Haus", "laufen", "Brücke"], "de")
    assert covered == {"haus", "laufen"}  # "Brücke" no aparece → no cubierto


def test_empty_targets_returns_empty():
    assert verify_coverage(_content("Hallo."), [], "de") == set()
