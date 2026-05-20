import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from klara.i18n import language_label
from klara.llm.base import LLMClient, Message
from klara.llm.prompts import STORY_USER_PROMPT, build_story_system_prompt
from klara.models import Story, VocabItem
from klara.models.enums import CEFRLevel, PartOfSpeech

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


def _parse_gender(value: str | None, *, target_language: str) -> str | None:
    if target_language != "de" or not value:
        return None
    v = value.strip().lower()
    if v in {"der", "die", "das"}:
        return v
    return None


# Articles per language. The German set is split because der/die/das also feed
# the `gender` field; the others are best-effort cleanup defensive against LLM
# noise even though the prompt forbids articles in `lemma`.
_GERMAN_GENDERED_ARTICLES = {"der", "die", "das"}
_LEADING_ARTICLES: dict[str, set[str]] = {
    "en": {"the", "a", "an"},
    "fr": {"le", "la", "les", "un", "une", "des"},
    "es": {"el", "la", "los", "las", "un", "una", "unos", "unas"},
    "pt": {"o", "a", "os", "as", "um", "uma", "uns", "umas"},
}
_FRENCH_ELISION_PREFIXES = ("l'", "l’", "d'", "d’")


def _strip_leading_article(text: str, articles: set[str]) -> str:
    parts = text.split(maxsplit=1)
    if len(parts) == 2 and parts[0].lower() in articles:
        return parts[1]
    return text


def _clean_lemma(lemma: str, *, target_language: str) -> tuple[str, str | None]:
    cleaned = lemma.strip().lstrip("•").strip()
    if target_language == "de":
        parts = cleaned.split(maxsplit=1)
        if len(parts) == 2 and parts[0].lower() in _GERMAN_GENDERED_ARTICLES:
            return parts[1], parts[0].lower()
        return cleaned, None
    if target_language == "fr":
        lower = cleaned.lower()
        for prefix in _FRENCH_ELISION_PREFIXES:
            if lower.startswith(prefix) and len(cleaned) > len(prefix):
                cleaned = cleaned[len(prefix) :]
                break
    articles = _LEADING_ARTICLES.get(target_language)
    if articles:
        cleaned = _strip_leading_article(cleaned, articles)
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
    *,
    target_language: str,
    native_language: str,
) -> list[VocabItem]:
    if not target_words:
        return []

    saved: list[VocabItem] = []
    for w in target_words:
        raw_lemma = (w.get("lemma") or "").strip()
        if not raw_lemma:
            continue
        pos = _parse_pos(w.get("pos"))
        lemma, inferred_gender = _clean_lemma(raw_lemma, target_language=target_language)
        gender = _parse_gender(w.get("gender"), target_language=target_language) or inferred_gender

        translation = (w.get("translation") or "").strip() or None
        translations = {native_language: translation} if translation else {}

        stmt = pg_insert(VocabItem).values(
            lemma=lemma,
            language=target_language,
            pos=pos,
            gender=gender,
            plural=w.get("plural") or None,
            translations=translations,
            example_target=w.get("example_target") or None,
            cefr_level=level,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_vocab_lemma_lang_pos",
            set_={
                "translations": VocabItem.translations.op("||")(stmt.excluded.translations),
                "example_target": stmt.excluded.example_target,
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
    target_language: str,
    native_language: str,
    learning_context: str | None,
    topic: str | None,
    model: str | None,
) -> GeneratedStory:
    target_label = language_label(target_language)
    native_label = language_label(native_language)
    recent = await _recent_vocab_lemmas(db, user_id)
    system = build_story_system_prompt(
        target_label=target_label,
        native_label=native_label,
        level=level.value,
        target_language=target_language,
        learning_context=learning_context,
    )
    user = STORY_USER_PROMPT.format(
        topic=topic or "libre — algo cotidiano",
        target_label=target_label,
        recent_vocab=", ".join(recent) if recent else "(ninguno)",
    )

    log.info(
        "story.generate.request",
        user_id=str(user_id),
        level=level.value,
        target_language=target_language,
        native_language=native_language,
        topic=topic,
    )
    response = await llm.complete(
        messages=[Message("system", system), Message("user", user)],
        model=model,
        max_tokens=4000,
        temperature=0.8,
        response_format={"type": "json_object"},
    )

    data = _extract_json(response.content)

    title = (data.get("title") or "Eine kleine Geschichte").strip()
    sentences = data.get("sentences") or []
    questions = data.get("comprehension_questions") or []
    target_words_raw = data.get("target_words") or []
    # quiz_items and insight are newer fields. They may be missing from
    # historical prompts or trimmed by the LLM; downstream code treats them
    # as best-effort and lazily backfills via dedicated endpoints.
    quiz_items_raw = data.get("quiz_items") or None
    insight_raw = data.get("insight") or None
    insight_title = None
    insight_body = None
    if isinstance(insight_raw, dict):
        t = insight_raw.get("title")
        b = insight_raw.get("body")
        if isinstance(t, str) and t.strip():
            insight_title = t.strip()[:200]
        if isinstance(b, str) and b.strip():
            insight_body = b.strip()[:2000]

    target_words = await _upsert_vocab_items(
        db,
        target_words_raw,
        level,
        target_language=target_language,
        native_language=native_language,
    )

    story = Story(
        user_id=user_id,
        level=level,
        target_language=target_language,
        native_language=native_language,
        title=title,
        content={"sentences": sentences, "comprehension_questions": questions},
        target_vocab_item_ids=[w.id for w in target_words],
        generated_by_provider=response.provider,
        generated_by_model=response.model,
        generation_cost_usd=response.cost_usd,
        quiz_items=quiz_items_raw if isinstance(quiz_items_raw, list) else None,
        insight_title=insight_title,
        insight_body=insight_body,
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
