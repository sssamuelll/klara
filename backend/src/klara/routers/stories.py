from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from sqlalchemy import select

from klara.dependencies import CurrentUser, DBSession, LocaleDep, SettingsDep, StoryLLM
from klara.i18n import t
from klara.models import Story, VocabItem
from klara.schemas.story import (
    ComprehensionQuestionOut,
    StoryContent,
    StoryCreateRequest,
    StoryListItem,
    StoryOut,
    StorySentenceOut,
    StoryWordOut,
)
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
    background.add_task(precache_texts, settings, texts)
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
