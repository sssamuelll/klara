from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from sqlalchemy import select

from klara.dependencies import ChatLLM, CurrentUser, DBSession, LocaleDep, SettingsDep, StoryLLM
from klara.i18n import t
from klara.models import PronunciationAttempt, QuizAttempt, Story, UserCard, VocabItem
from klara.schemas.finish import (
    InsightOut,
    PronunciationAttemptIn,
    PronunciationAttemptOut,
    QuizAttemptIn,
    QuizAttemptOut,
    QuizOut,
    ScheduleBucket,
    ScheduleEntry,
    ScheduleOut,
)
from klara.schemas.story import (
    ComprehensionQuestionOut,
    StoryContent,
    StoryCreateRequest,
    StoryListItem,
    StoryOut,
    StorySentenceOut,
    StoryWordOut,
)
from klara.services.finish_lessons import ensure_insight, ensure_quiz_items
from klara.services.story_gen import generate_story
from klara.services.tts_precache import collect_story_texts, precache_texts

router = APIRouter(prefix="/stories", tags=["stories"])


def _serialize_story(story: Story, words: list[VocabItem], native_language: str) -> StoryOut:
    content = story.content or {}
    sentences = [StorySentenceOut(**s) for s in content.get("sentences", [])]
    questions = [ComprehensionQuestionOut(**q) for q in content.get("comprehension_questions", [])]
    target = [
        StoryWordOut(
            id=w.id,
            lemma=w.lemma,
            pos=w.pos,
            gender=w.gender,
            plural=w.plural,
            translation=(w.translations or {}).get(native_language),
            example_target=w.example_target,
        )
        for w in words
    ]
    return StoryOut(
        id=story.id,
        level=story.level,
        target_language=story.target_language,
        native_language=story.native_language,
        title=story.title,
        content=StoryContent(sentences=sentences, comprehension_questions=questions),
        target_words=target,
        generated_by_provider=story.generated_by_provider,
        generated_by_model=story.generated_by_model,
        generation_cost_usd=story.generation_cost_usd,
        created_at=story.created_at,
    )


async def _load_words(db, ids: list[UUID]) -> list[VocabItem]:
    if not ids:
        return []
    rows = (await db.execute(select(VocabItem).where(VocabItem.id.in_(ids)))).scalars().all()
    by_id = {w.id: w for w in rows}
    return [by_id[i] for i in ids if i in by_id]


@router.post("", response_model=StoryOut, status_code=status.HTTP_201_CREATED)
async def create_story(
    payload: StoryCreateRequest,
    db: DBSession,
    user: CurrentUser,
    llm: StoryLLM,
    settings: SettingsDep,
    background: BackgroundTasks,
) -> StoryOut:
    level = payload.level or user.level
    result = await generate_story(
        db,
        llm,
        user_id=user.id,
        level=level,
        target_language=user.target_language,
        native_language=user.native_language,
        learning_context=user.learning_context,
        topic=payload.topic,
        model=None,
    )
    serialized = _serialize_story(result.story, result.target_words, user.native_language)
    target_words_dicts = [
        {"lemma": w.lemma, "example_target": w.example_target} for w in result.target_words
    ]
    texts = collect_story_texts(result.story.content, target_words_dicts)
    if serialized.title:
        texts = [serialized.title] + [t for t in texts if t != serialized.title]
    background.add_task(precache_texts, settings, texts, result.story.target_language)
    return serialized


@router.get("", response_model=list[StoryListItem])
async def list_stories(
    db: DBSession,
    user: CurrentUser,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[StoryListItem]:
    # Filter by current target_language so home / lists never surface stories
    # the user can no longer practice. get_story() still serves any owned story
    # by id, so direct URLs to old-target stories keep working.
    stmt = (
        select(Story)
        .where(
            Story.user_id == user.id,
            Story.target_language == user.target_language,
        )
        .order_by(Story.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        StoryListItem(
            id=s.id,
            level=s.level,
            target_language=s.target_language,
            title=s.title,
            created_at=s.created_at,
        )
        for s in rows
    ]


@router.get("/{story_id}", response_model=StoryOut)
async def get_story(
    story_id: UUID, db: DBSession, user: CurrentUser, locale: LocaleDep
) -> StoryOut:
    story = await db.get(Story, story_id)
    if story is None or story.user_id != user.id:
        raise HTTPException(status_code=404, detail=t("errors.story_not_found", locale))
    words = await _load_words(db, list(story.target_vocab_item_ids or []))
    return _serialize_story(story, words, user.native_language)


async def _load_or_404(db, story_id: UUID, user_id: UUID, locale: str) -> Story:
    story = await db.get(Story, story_id)
    if story is None or story.user_id != user_id:
        raise HTTPException(status_code=404, detail=t("errors.story_not_found", locale))
    return story


@router.get("/{story_id}/quiz", response_model=QuizOut)
async def get_story_quiz(
    story_id: UUID,
    db: DBSession,
    user: CurrentUser,
    locale: LocaleDep,
    llm: ChatLLM,
) -> QuizOut:
    story = await _load_or_404(db, story_id, user.id, locale)
    words = await _load_words(db, list(story.target_vocab_item_ids or []))
    lemmas = [w.lemma for w in words]
    items = await ensure_quiz_items(db, story, llm, lemmas=lemmas)
    return QuizOut(items=items or [])


@router.get("/{story_id}/insight", response_model=InsightOut | None)
async def get_story_insight(
    story_id: UUID,
    db: DBSession,
    user: CurrentUser,
    locale: LocaleDep,
    llm: ChatLLM,
) -> InsightOut | None:
    story = await _load_or_404(db, story_id, user.id, locale)
    words = await _load_words(db, list(story.target_vocab_item_ids or []))
    lemmas = [w.lemma for w in words]
    result = await ensure_insight(db, story, llm, lemmas=lemmas)
    if result is None:
        return None
    title, body = result
    return InsightOut(title=title, body=body)


@router.post(
    "/{story_id}/pronunciation/attempts",
    response_model=PronunciationAttemptOut,
    status_code=status.HTTP_201_CREATED,
)
async def record_pronunciation_attempt(
    story_id: UUID,
    payload: PronunciationAttemptIn,
    db: DBSession,
    user: CurrentUser,
    locale: LocaleDep,
) -> PronunciationAttemptOut:
    await _load_or_404(db, story_id, user.id, locale)
    row = PronunciationAttempt(
        user_id=user.id,
        story_id=story_id,
        sentence_index=payload.sentence_index,
        reference_text=payload.reference_text,
        recognized_text=payload.recognized_text,
        overall_score=payload.overall_score,
        word_bands=payload.word_bands,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return PronunciationAttemptOut(
        id=row.id,
        sentence_index=row.sentence_index,
        overall_score=row.overall_score,
        attempted_at=row.attempted_at,
    )


def _bucket_for(next_review_at: datetime | None) -> ScheduleBucket:
    """Map a card's next_review_at to one of the human-label buckets the
    frontend renders. Thresholds live here so all clients format identically.
    """
    if next_review_at is None:
        return "due_now"
    if next_review_at.tzinfo is None:
        next_review_at = next_review_at.replace(tzinfo=UTC)
    delta = (next_review_at - datetime.now(UTC)).total_seconds() / 86400.0  # days
    if delta <= 1:
        return "due_now"
    if delta <= 3:
        return "soon"
    if delta <= 7:
        return "this_week"
    if delta <= 14:
        return "next_week"
    return "later"


@router.get("/{story_id}/schedule", response_model=ScheduleOut)
async def get_story_schedule(
    story_id: UUID,
    db: DBSession,
    user: CurrentUser,
    locale: LocaleDep,
) -> ScheduleOut:
    """Per-target-word SRS state for the Finish summary's Schedule section.

    Returns one entry per vocab_item_id in the story's `target_vocab_item_ids`,
    preserving order. The frontend localises the bucket into a label and
    overlays an in-session "struggled" tag from this-session scores.
    """
    story = await _load_or_404(db, story_id, user.id, locale)
    target_ids = list(story.target_vocab_item_ids or [])
    if not target_ids:
        return ScheduleOut(entries=[])

    cards = (
        (
            await db.execute(
                select(UserCard).where(
                    UserCard.user_id == user.id,
                    UserCard.vocab_item_id.in_(target_ids),
                )
            )
        )
        .scalars()
        .all()
    )
    by_vocab: dict[UUID, UserCard] = {c.vocab_item_id: c for c in cards}

    entries: list[ScheduleEntry] = []
    for vid in target_ids:
        card = by_vocab.get(vid)
        if card is None:
            entries.append(ScheduleEntry(vocab_item_id=vid, has_card=False, bucket="not_in_srs"))
            continue
        entries.append(
            ScheduleEntry(
                vocab_item_id=vid,
                has_card=True,
                bucket=_bucket_for(card.next_review_at),
                next_review_at=card.next_review_at,
            )
        )
    return ScheduleOut(entries=entries)


@router.post(
    "/{story_id}/quiz/attempts",
    response_model=QuizAttemptOut,
    status_code=status.HTTP_201_CREATED,
)
async def record_quiz_attempt(
    story_id: UUID,
    payload: QuizAttemptIn,
    db: DBSession,
    user: CurrentUser,
    locale: LocaleDep,
) -> QuizAttemptOut:
    await _load_or_404(db, story_id, user.id, locale)
    row = QuizAttempt(
        user_id=user.id,
        story_id=story_id,
        question_index=payload.question_index,
        question_type=payload.question_type,
        was_correct=payload.was_correct,
        was_revealed=payload.was_revealed,
        detail=payload.detail,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return QuizAttemptOut(
        id=row.id,
        question_index=row.question_index,
        question_type=row.question_type,
        was_correct=row.was_correct,
        was_revealed=row.was_revealed,
        attempted_at=row.attempted_at,
    )
