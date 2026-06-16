"""¿La historia generada REALMENTE contiene los lemas objetivo pedidos?

Sin esto el currículo alucina niveles en silencio. Tokeniza con el tokenizador
canónico del repo, lematiza cada token, y devuelve qué lemas objetivo aparecen.
"""

from __future__ import annotations

from klara.curriculum.lemmatize import canonical_lemma
from klara.services.tokens import word_tokens_by_index


def verify_coverage(content: dict, lemmas: list[str], language: str) -> set[str]:
    """Subconjunto de `lemmas` (canónicos) presente en el contenido de la historia."""
    targets = {canonical_lemma(lemma, language) for lemma in lemmas if lemma}
    if not targets:
        return set()
    seen: set[str] = set()
    for sentence in content.get("sentences", []) or []:
        if not isinstance(sentence, dict):
            continue  # el JSON del LLM puede traer entradas malformadas
        text = sentence.get("target") or ""
        for token in word_tokens_by_index(text).values():
            seen.add(canonical_lemma(token, language))
        for entry in sentence.get("breakdown") or []:
            word = entry.get("word") if isinstance(entry, dict) else None
            if isinstance(word, str):
                seen.add(canonical_lemma(word, language))
    return targets & seen
