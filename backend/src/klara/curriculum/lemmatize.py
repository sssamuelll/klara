"""Lematizador canónico por idioma sobre simplemma.

Mapea una forma de superficie a su lema canónico EN MINÚSCULAS, para que el
conteo de cobertura y el known-set agrupen flexiones bajo una familia. Para un
idioma que simplemma no soporta, degrada a la identidad en minúsculas (nunca
crashea): la secuencia de ese idioma sigue genérica (deuda visible, spec §10).
"""

from __future__ import annotations

import simplemma


def canonical_lemma(word: str, language: str) -> str:
    # NO bajar a minúsculas ANTES de lematizar: simplemma usa la mayúscula inicial
    # del sustantivo alemán como señal de su categoría (Tische→tisch, Haus→haus).
    # Forzar minúsculas primero lo trata como verbo y sobre-lematiza
    # (Tische→tischen, Haus→hausen). Lematiza sobre la forma original; baja DESPUÉS.
    w = word.strip()
    if not w:
        return ""
    try:
        return simplemma.lemmatize(w, lang=language).lower()
    except (ValueError, KeyError):
        # idioma no soportado por simplemma → identidad en minúsculas
        return w.lower()
