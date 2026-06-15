"""Registro de ejes de competencia por idioma.

Declarar los ejes (no poblarlos todos) es el compromiso del modelo híbrido: el
espacio de competencia de cada idioma queda nombrado, y v1 solo puebla
`lexical`. Los ejes gramaticales/ortográficos existen como forma, no código
muerto; la Rebanada 2 (género) implementa el primero sobre la misma interfaz.
"""

from __future__ import annotations

LANGUAGE_AXES: dict[str, list[str]] = {
    "de": ["lexical", "gender", "case", "word_order"],
    "ja": ["lexical", "orthography", "particles", "pitch"],
    "en": ["lexical"],
    "fr": ["lexical"],
    "pt": ["lexical"],
    "es": ["lexical"],
}


def axes_for(language: str) -> list[str]:
    """Ejes declarados de un idioma; cae a sólo léxico si no está registrado."""
    return LANGUAGE_AXES.get(language, ["lexical"])
