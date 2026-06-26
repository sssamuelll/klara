"""LLM-backed corrective pronunciation tip for the single worst mispronounced word.

Clone of the phonetic_hints discipline (strict JSON, best-effort), plus a
cache/analytics row keyed by (native_language, target_language, word,
weakest IPA phoneme). On any failure the tip is empty and the caller keeps
showing the stress hint.
"""

from __future__ import annotations

import json

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from klara.i18n.languages import language_label
from klara.llm.base import LLMClient, Message
from klara.models.pronunciation_diagnosis import PronunciationDiagnosis
from klara.pronunciation.schemas import DiagnoseResponse, PhonemeScore
from klara.services.phonetic_hints import _extract_json

log = structlog.get_logger(__name__)

_SYSTEM_PROMPT = """You are a pronunciation coach. The learner's native language is {native_label}.
They mispronounced the {target_label} word «{word}»; the weakest sound was the IPA phoneme /{phoneme}/.

Write ONE corrective tip:
- ≤25 words, written in {native_label}.
- Concrete and physical: lips, tongue, jaw, airflow, rhythm — or a comparison to a {native_label} sound.
- Tell them what to DO. Never "try again", never abstract.

Return STRICT JSON only: {{"tip": "..."}}"""


def _short(lang: str) -> str:
    return lang.split("-")[0].lower()


async def generate_diagnosis(
    llm: LLMClient,
    db: AsyncSession,
    *,
    word: str,
    phonemes: list[PhonemeScore],
    target_language: str,
    native_language: str,
) -> DiagnoseResponse:
    if not phonemes:
        return DiagnoseResponse()
    weakest = min(phonemes, key=lambda p: p.accuracy_score)

    key_word = word.strip().lower()
    nl = _short(native_language)
    tl = _short(target_language)
    if not key_word:
        return DiagnoseResponse()

    existing = (
        await db.execute(
            select(PronunciationDiagnosis).where(
                PronunciationDiagnosis.native_language == nl,
                PronunciationDiagnosis.target_language == tl,
                PronunciationDiagnosis.word == key_word,
                PronunciationDiagnosis.weakest_phoneme == weakest.phoneme,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.hit_count += 1
        await db.commit()
        return DiagnoseResponse(tip=existing.tip, weakest_phoneme=existing.weakest_phoneme)

    system = _SYSTEM_PROMPT.format(
        native_label=language_label(nl),
        target_label=language_label(tl),
        word=word.strip(),
        phoneme=weakest.phoneme,
    )
    resp = await llm.complete(
        messages=[Message(role="system", content=system), Message(role="user", content="Give the tip.")],
        max_tokens=128,
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    try:
        payload = _extract_json(resp.content)
    except (ValueError, json.JSONDecodeError) as e:
        log.warning("diagnose.parse_failed", error=str(e), raw=resp.content[:300])
        return DiagnoseResponse()

    tip = payload.get("tip")
    if not isinstance(tip, str) or not tip.strip():
        return DiagnoseResponse()
    tip = tip.strip()[:400]

    db.add(
        PronunciationDiagnosis(
            native_language=nl, target_language=tl, word=key_word,
            weakest_phoneme=weakest.phoneme, phoneme_score=weakest.accuracy_score, tip=tip,
        )
    )
    await db.commit()
    return DiagnoseResponse(tip=tip, weakest_phoneme=weakest.phoneme)
