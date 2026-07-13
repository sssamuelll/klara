"""Rule-based German lint gate for generated story content.

The single-user failure mode Duolingo's population catches and Klara can't
(consenso 2026-07-13): agrammatical German reaching the only user, with no
crowd to flag it. Deterministic rules over the curated oracle only — no LLM
judging LLM. Under-flagging is the designed failure mode: a violation must be
PROVABLE from the lexicon; a miss is fine, a false positive is not."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from klara.models import GenderLexicon
from klara.services.tokens import word_tokens_by_index

# Definite-article surface forms that are grammatical SOMEWHERE in the
# declension table (nom/acc/dat/gen) of each oracle gender. An article is
# evidence of error only when it fits NO case of the oracle gender:
# "die Haus" can never be right; "der Frau" is dative feminine and fine.
# Residual aceptado: los adjetivos nominalizados son multi-género en superficie
# (der/die/das Deutsche) mientras el léxico guarda UN género por lema
# (first-genus-wins), así que una forma gramatical podría en principio
# flaggearse según el contenido del léxico — mismo blast radius (pool-block,
# nunca user-facing).
_VALID_ARTICLES: dict[str, set[str]] = {
    "der": {"der", "den", "dem", "des"},
    "die": {"die", "der"},
    "das": {"das", "dem", "des"},
}
_DEFINITE_ARTICLES = {"der", "die", "das"}

# Sufijos de plural-cero: el plural es idéntico al lema (die Mädchen, der
# Fenster genitivo...), así que un hit exacto en el oráculo puede ser una
# lectura plural gramatical. die/der + estos sufijos → skip (under-flag by
# design); "das" nunca acompaña plurales, así que conserva el chequeo entero.
_ZERO_PLURAL_SUFFIXES = ("chen", "lein", "er", "el", "en")


async def _oracle_gender_exact(db: AsyncSession, noun: str) -> str | None:
    """Exact/case-insensitive lexicon hit ONLY. resolve_gender's compound
    fallback is deliberately not used here: on inflected forms it
    false-positives ("Kinder" suffix-matches "Inder" → der), and a gate must
    never flag grammatical text."""
    row = await db.get(GenderLexicon, noun)
    if row is not None:
        return row.gender
    return (
        await db.execute(
            select(GenderLexicon.gender)
            .where(func.lower(GenderLexicon.lemma) == noun.lower())
            .limit(1)
        )
    ).scalar_one_or_none()


async def gender_article_violations(db: AsyncSession, content: dict, *, language: str) -> list[str]:
    """Article+noun bigrams whose article fits NO case of the noun's oracle
    gender. Returns human-readable violations ("die Haus (oracle: das)"),
    in reading order. Empty for non-German content."""
    if language != "de":
        return []
    violations: list[str] = []
    for sentence in content.get("sentences", []) or []:
        if not isinstance(sentence, dict):
            continue  # el JSON del LLM puede traer entradas malformadas
        # Los ÍNDICES cuentan TODOS los tokens (palabra/espacio/puntuación) —
        # ver word_tokens_by_index. Dos palabras separadas solo por un espacio
        # distan exactamente 2; cualquier puntuación entre medio abre el gap.
        items = sorted(word_tokens_by_index(sentence.get("target") or "").items())
        for k in range(len(items) - 1):
            art_idx, art = items[k]
            noun_idx, noun = items[k + 1]
            a = art.lower()
            if a not in _DEFINITE_ARTICLES or not noun[:1].isupper():
                continue
            if a in {"die", "der"} and noun.lower().endswith(_ZERO_PLURAL_SUFFIXES):
                continue  # posible lectura plural gramatical — skip
            # Techo aceptado: una coma sin espacio ("Mann,der") tokeniza sin
            # gap y derrota esta heurística de índices — cerrarlo requiere
            # TIPOS de token, que word_tokens_by_index no expone. Consecuencia:
            # pool-block solamente.
            if noun_idx - art_idx != 2:
                continue  # puntuación entre artículo y sustantivo — no es bigrama
            # Un der/die/das precedido de puntuación puede ser PRONOMBRE
            # RELATIVO, no artículo: la cláusula relativa alemana EXIGE coma
            # antes ("Der Mann, der Brot kauft"). Saltarlo — under-flag by
            # design. Artículo inicial de oración (sin palabra previa) sí se
            # chequea: una relativa nunca abre oración.
            if k > 0 and art_idx - items[k - 1][0] > 2:
                continue
            oracle = await _oracle_gender_exact(db, noun)
            if oracle is not None and a not in _VALID_ARTICLES[oracle]:
                violations.append(f"{art} {noun} (oracle: {oracle})")
    return violations
