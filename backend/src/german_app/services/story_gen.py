import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from german_app.llm.base import LLMClient, Message
from german_app.llm.prompts import STORY_SYSTEM_PROMPT, STORY_USER_PROMPT
from german_app.models import Story, VocabItem
from german_app.models.enums import CEFRLevel, PartOfSpeech

log = structlog.get_logger(__name__)


@dataclass(slots=True)
class GeneratedStory:
    story: Story
    target_words: list[VocabItem]


def _parse_pos(value: str | None) -> PartOfSpeech:
    if not value:
        return PartOfSpeech.OTHER
    try:
        return PartOfSpeech(value.lower())
    except ValueError:
        return PartOfSpeech.OTHER


def _parse_gender(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip().lower()
    if v in {"der", "die", "das"}:
        return v
    return None


def _clean_lemma(lemma: str) -> tuple[str, str | None]:
    cleaned = lemma.strip().lstrip("•").strip()
    parts = cleaned.split(maxsplit=1)
    if len(parts) == 2 and parts[0].lower() in {"der", "die", "das"}:
        return parts[1], parts[0].lower()
    return cleaned, None


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in LLM response")
    return json.loads(text[start : end + 1])


async def _upsert_vocab_items(
    db: AsyncSession,
    target_words: list[dict[str, Any]],
    level: CEFRLevel,
) -> list[VocabItem]:
    if not target_words:
        return []

    saved: list[VocabItem] = []
    for w in target_words:
        raw_lemma = (w.get("lemma") or "").strip()
        if not raw_lemma:
            continue
        pos = _parse_pos(w.get("pos"))
        lemma, inferred_gender = _clean_lemma(raw_lemma)
        gender = _parse_gender(w.get("gender")) or inferred_gender

        stmt = pg_insert(VocabItem).values(
            lemma=lemma,
            language="de",
            pos=pos,
            gender=gender,
            plural=w.get("plural") or None,
            translation_es=w.get("translation_es") or None,
            example_de=w.get("example_de") or None,
            cefr_level=level,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_vocab_lemma_lang_pos",
            set_={
                "translation_es": stmt.excluded.translation_es,
                "example_de": stmt.excluded.example_de,
                "gender": stmt.excluded.gender,
                "plural": stmt.excluded.plural,
            },
        ).returning(VocabItem.id)
        result = await db.execute(stmt)
        vocab_id = result.scalar_one()

        item = await db.get(VocabItem, vocab_id)
        if item is not None:
            saved.append(item)
    return saved


async def _recent_vocab_lemmas(db: AsyncSession, user_id: UUID, limit: int = 25) -> list[str]:
    recent_stmt = (
        select(Story.target_vocab_item_ids)
        .where(Story.user_id == user_id)
        .order_by(Story.created_at.desc())
        .limit(5)
    )
    rows = (await db.execute(recent_stmt)).all()
    ids: list[UUID] = []
    for row in rows:
        ids.extend(row[0] or [])
    if not ids:
        return []
    unique_ids = list(dict.fromkeys(ids))[:limit]
    lemma_stmt = select(VocabItem.lemma).where(VocabItem.id.in_(unique_ids))
    return [r[0] for r in (await db.execute(lemma_stmt)).all()]


async def generate_story(
    db: AsyncSession,
    llm: LLMClient,
    *,
    user_id: UUID,
    level: CEFRLevel,
    native_language: str,
    topic: str | None,
    model: str | None,
) -> GeneratedStory:
    recent = await _recent_vocab_lemmas(db, user_id)
    system = STORY_SYSTEM_PROMPT.format(native_language=native_language, level=level.value)
    user = STORY_USER_PROMPT.format(
        topic=topic or "libre — algo cotidiano de Nürnberg",
        recent_vocab=", ".join(recent) if recent else "(ninguno)",
    )

    log.info("story.generate.request", user_id=str(user_id), level=level.value, topic=topic)
    response = await llm.complete(
        messages=[Message("system", system), Message("user", user)],
        model=model,
        max_tokens=1500,
        temperature=0.8,
        response_format={"type": "json_object"},
    )

    data = _extract_json(response.content)

    title = (data.get("title") or "Eine kleine Geschichte").strip()
    sentences = data.get("sentences") or []
    questions = data.get("comprehension_questions") or []
    target_words_raw = data.get("target_words") or []

    target_words = await _upsert_vocab_items(db, target_words_raw, level)

    story = Story(
        user_id=user_id,
        level=level,
        title=title,
        content={"sentences": sentences, "comprehension_questions": questions},
        target_vocab_item_ids=[w.id for w in target_words],
        generated_by_provider=response.provider,
        generated_by_model=response.model,
        generation_cost_usd=response.cost_usd,
    )
    db.add(story)
    await db.flush()
    await db.commit()
    await db.refresh(story)

    log.info(
        "story.generate.done",
        story_id=str(story.id),
        n_sentences=len(sentences),
        n_target_words=len(target_words),
        cost_usd=response.cost_usd,
    )
    return GeneratedStory(story=story, target_words=target_words)
