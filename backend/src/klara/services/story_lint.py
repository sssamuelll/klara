"""Rule-based German lint gate for generated story content.

The single-user failure mode Duolingo's population catches and Klara can't
(consenso 2026-07-13): agrammatical German reaching the only user, with no
crowd to flag it. Deterministic rules over the curated oracle only — no LLM
judging LLM. Under-flagging is the designed failure mode: a violation must be
PROVABLE from the lexicon; a miss is fine, a false positive is not."""

from __future__ import annotations

from itertools import pairwise

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from klara.models import GenderLexicon
from klara.services.tokens import word_tokens_by_index

# Definite-article surface forms that are grammatical SOMEWHERE in the
# declension table (nom/acc/dat/gen) of each oracle gender. An article is
# evidence of error only when it fits NO case of the oracle gender:
# "die Haus" can never be right; "der Frau" is dative feminine and fine.
_VALID_ARTICLES: dict[str, set[str]] = {
    "der": {"der", "den", "dem", "des"},
    "die": {"die", "der"},
    "das": {"das", "dem", "des"},
}
_DEFINITE_ARTICLES = {"der", "die", "das"}


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
        tokens = list(word_tokens_by_index(sentence.get("target") or "").values())
        for art, noun in pairwise(tokens):
            a = art.lower()
            if a not in _DEFINITE_ARTICLES or not noun[:1].isupper():
                continue
            oracle = await _oracle_gender_exact(db, noun)
            if oracle is not None and a not in _VALID_ARTICLES[oracle]:
                violations.append(f"{art} {noun} (oracle: {oracle})")
    return violations
