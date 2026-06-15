"""Tokenizador canónico del repo + ranking de bandas.

Fuente única de verdad para la tokenización palabra/espacio/puntuación. El
frontend (`frontend/src/lib/pronunciation.ts`) DEBE espejar `_PUNCT` byte a byte
— los índices de `word_bands` se alinean entre cliente y servidor solo si ambos
tokenizan idéntico (spec §6.2). Si cambias `_PUNCT`, cambia las copias del
frontend y corre el smoke de pronunciación con una frase con comillas curvas.
"""

from __future__ import annotations

import re

# Clase de puntuación canónica. Reproduce EXACTAMENTE lo capturado en Task 1
# Step 1. Codepoints: ASCII . , ! ? ; : ( ) - · U+00A1 U+00BF (¡ ¿) ·
# U+2014 U+2013 (em/en dash) · U+00BB U+00AB (» «) · U+201E U+201C U+201D
# (apertura/cierre de comillas tipográficas).
_PUNCT = r".,!?;:„“”»«()¡¿—–\-"
_TOKEN_RE = re.compile(rf"(\s+)|([{_PUNCT}]+)|([^\s{_PUNCT}]+)")

# Ranking de bandas, peor -> mejor. Banda desconocida ordena al final (segura).
BAND_RANK: dict[str, int] = {"bad": 0, "ok": 1, "good": 2}


def word_tokens_by_index(text: str) -> dict[int, str]:
    """{índice_global_de_token: texto_de_palabra} solo para tokens de palabra.

    El índice cuenta TODOS los tokens (espacio, puntuación, palabra) para que
    coincida con las llaves de `word_bands` producidas por el frontend.
    """
    out: dict[int, str] = {}
    i = 0
    for m in _TOKEN_RE.finditer(text):
        if m.group(3):  # token de palabra
            out[i] = m.group(3)
        i += 1
    return out


def worst_band(word_bands: dict[int, str]) -> str | None:
    """La peor banda presente (por BAND_RANK), o None si no hay ninguna."""
    if not word_bands:
        return None
    return min(word_bands.values(), key=lambda b: BAND_RANK.get(b, 99))
