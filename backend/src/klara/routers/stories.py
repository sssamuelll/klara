import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from starlette.concurrency import run_in_threadpool

from klara.curriculum.competence import gender_weakness_order
from klara.curriculum.gender_eligibility import is_gender_eligible
from klara.curriculum.library import advance_module_if_completed, maybe_recycle_to_library
from klara.curriculum.modules import (
    enroll_cards,
    ensure_active_module,
    module_target_lemmas,
    module_vocab_ids,
)
from klara.curriculum.selection import next_target_words
from klara.dependencies import ChatLLM, CurrentUser, DBSession, LocaleDep, SettingsDep, StoryLLM
from klara.i18n import language_label, t
from klara.i18n.languages import SUPPORTED_LANGUAGES, speech_locale
from klara.models import (
    GenderL1Note,
    Module,
    PronunciationAttempt,
    QuizAttempt,
    Story,
    StoryView,
    UserCard,
    VocabItem,
)
from klara.pronunciation.audio import FfmpegMissingError, TranscodeError, transcode_to_wav
from klara.pronunciation.azure_client import AzureSpeechError
from klara.pronunciation.stt_client import transcribe
from klara.schemas.finish import (
    GenderL1NoteItem,
    GenderL1NotesOut,
    InsightOut,
    KlaraNoteOut,
    MCResolveOut,
    PronunciationAttemptIn,
    PronunciationAttemptOut,
    QuizAttemptIn,
    QuizAttemptOut,
    QuizOut,
    ScheduleBucket,
    ScheduleEntry,
    ScheduleOut,
    StoryFinishOut,
)
from klara.schemas.gender import GenderAttemptIn, GenderAttemptOut
from klara.schemas.story import (
    ComprehensionQuestionOut,
    StoryContent,
    StoryCreateRequest,
    StoryListItem,
    StoryOut,
    StorySentenceOut,
    StoryWordOut,
)
from klara.services.finish_lessons import (
    build_gender_cloze,
    ensure_insight,
    ensure_klara_note,
    ensure_quiz_items,
)
from klara.services.gender_grading import grade_gender_attempt
from klara.services.story_gen import StoryGenerationError, generate_story
from klara.services.tts_precache import collect_story_texts, precache_texts
from klara.services.voice_mc import resolve_option

router = APIRouter(prefix="/stories", tags=["stories"])
log = structlog.get_logger(__name__)


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
            frequency_rank=w.frequency_rank,
        )
        for w in words
    ]
    ranked = [w for w in words if w.frequency_rank is not None]
    if ranked:
        lemmas = ", ".join(w.lemma for w in ranked)
        curriculum_note = (
            f"Estas palabras están entre las más comunes en {language_label(story.target_language)} "
            f"que aún no dominas: {lemmas}."
        )
    else:
        curriculum_note = None
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
        curriculum_note=curriculum_note,
        module_id=story.module_id,
    )


async def _load_words(db, ids: list[UUID]) -> list[VocabItem]:
    if not ids:
        return []
    rows = (await db.execute(select(VocabItem).where(VocabItem.id.in_(ids)))).scalars().all()
    by_id = {w.id: w for w in rows}
    return [by_id[i] for i in ids if i in by_id]


def _module_objective(module) -> str:
    """Build the module objective block injected into the story prompt."""
    can_dos = "; ".join(module.can_dos or [])
    focus = "; ".join(module.grammatical_focus or [])
    parts = ["OBJETIVO DEL MÓDULO (la historia debe servir este objetivo, sin forzar):"]
    if can_dos:
        parts.append(f"Can-do: {can_dos}.")
    if focus:
        parts.append(f"Foco gramatical: {focus}.")
    return " ".join(parts)


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
    if payload.module_id is not None:
        active = await db.get(Module, payload.module_id)
        if active is None or active.language != user.target_language:
            raise HTTPException(status_code=404, detail="module.not_found")
        # Starting a story in module M moves the pointer to M (gated suave).
        user.current_module_id = active.id
    else:
        active = await ensure_active_module(db, user)
    if active is not None:
        target_lemmas = await module_target_lemmas(db, active)
        mod_vids = await module_vocab_ids(db, active)
        objective = _module_objective(active)
    else:
        target_words_sel = await next_target_words(
            db, user_id=user.id, language=user.target_language, level=level, n=5
        )
        target_lemmas = [w.lemma for w in target_words_sel]
        mod_vids = set()
        objective = None

    try:
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
            target_lemmas=target_lemmas,
            module_objective=objective,
        )
    except StoryGenerationError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Story generation failed. Please try again.",
        ) from None

    if active is not None:
        enrolled = [w.id for w in result.target_words if w.id in mod_vids]
        await enroll_cards(db, user_id=user.id, vocab_item_ids=enrolled)
    result.story.module_id = active.id if active is not None else None
    # Pool growth is best-effort: never let it break story creation.
    try:
        await maybe_recycle_to_library(
            db,
            story=result.story,
            dropped_lemmas=result.dropped_lemmas,
            topic=payload.topic,
            topic_origin=payload.topic_origin,
        )
    except Exception:
        log.warning("library.pool.recycle_failed", story_id=str(result.story.id))
    # Single commit owns both the story (flushed in generate_story) and the
    # module enrollment — atomic: a failed enroll rolls back the story too.
    await db.commit()

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
    module_id: Annotated[UUID | None, Query()] = None,
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
    if module_id is not None:
        stmt = stmt.where(Story.module_id == module_id)
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
    items = list(await ensure_quiz_items(db, story, llm, lemmas=lemmas) or [])
    prefer = await gender_weakness_order(db, user_id=user.id, vocab_item_ids=[w.id for w in words])
    gender_cloze = build_gender_cloze(
        words, native_language=user.native_language, prefer_order=prefer
    )
    if gender_cloze is not None:
        items.append(gender_cloze)
    return QuizOut(items=items)


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


@router.get("/{story_id}/klara-note", response_model=KlaraNoteOut | None)
async def get_story_klara_note(
    story_id: UUID,
    db: DBSession,
    user: CurrentUser,
    locale: LocaleDep,
    llm: ChatLLM,
) -> KlaraNoteOut | None:
    """One-line teaser shown at the bottom of the Finish summary."""
    story = await _load_or_404(db, story_id, user.id, locale)
    body = await ensure_klara_note(db, story, llm)
    if body is None:
        return None
    return KlaraNoteOut(body=body)


@router.get("/{story_id}/gender/l1-notes", response_model=GenderL1NotesOut)
async def get_story_l1_notes(
    story_id: UUID,
    db: DBSession,
    user: CurrentUser,
    locale: LocaleDep,
) -> GenderL1NotesOut:
    """Curated ES<->DE gender-trap notes for the story's target words, keyed by the
    story's L1. The displayed der/die/das is oracle-gated; words without an
    authoritative oracle gender are dropped, so a note never rides an LLM guess."""
    story = await _load_or_404(db, story_id, user.id, locale)
    ids = list(story.target_vocab_item_ids or [])
    if not ids:
        return GenderL1NotesOut(notes=[])
    words = await _load_words(db, ids)
    # eligible[lower(lemma)] = oracle gender; German nouns with an authoritative gender only.
    eligible: dict[str, str] = {w.lemma.lower(): w.gender for w in words if is_gender_eligible(w)}
    if not eligible:
        return GenderL1NotesOut(notes=[])
    l1 = (story.native_language or "").lower()
    rows = (
        await db.execute(
            select(GenderL1Note.lemma, GenderL1Note.note).where(
                GenderL1Note.l1_language == l1,
                func.lower(GenderL1Note.lemma).in_(list(eligible.keys())),
            )
        )
    ).all()
    notes: list[GenderL1NoteItem] = []
    seen: set[str] = set()
    for note_lemma, note in rows:
        key = note_lemma.lower()
        gender = eligible.get(key)
        if gender is None or key in seen:
            continue
        seen.add(key)
        # Display the seed's (capitalized) lemma, not the possibly drifted VocabItem casing.
        notes.append(GenderL1NoteItem(lemma=note_lemma, gender=gender, note=note))
    return GenderL1NotesOut(notes=notes)


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


@router.post(
    "/{story_id}/gender/attempts",
    response_model=GenderAttemptOut,
    status_code=status.HTTP_201_CREATED,
)
async def record_gender_attempt(
    story_id: UUID,
    payload: GenderAttemptIn,
    db: DBSession,
    user: CurrentUser,
    locale: LocaleDep,
) -> GenderAttemptOut:
    """Grade a der/die/das pick against the oracle (VocabItem.gender) and record
    the diadic evidence. The story scopes which words are answerable, and grading
    is restricted to oracle-sourced genders so an LLM guess is never certified as
    evidence (the curriculum invariant: the source of truth must outrank the
    learner)."""
    story = await _load_or_404(db, story_id, user.id, locale)
    if payload.vocab_item_id not in (story.target_vocab_item_ids or []):
        raise HTTPException(status_code=404, detail=t("errors.vocab_not_found", locale))
    out = await grade_gender_attempt(
        db,
        user_id=user.id,
        vocab_item_id=payload.vocab_item_id,
        picked_article=payload.picked_article,
    )
    if out is None:
        raise HTTPException(status_code=404, detail=t("errors.vocab_not_found", locale))
    return out


def _resolve_bcp47(raw: str) -> str:
    if "-" in raw:
        return raw
    if raw in SUPPORTED_LANGUAGES:
        return speech_locale(raw)
    return raw


MCAudio = Annotated[UploadFile, File(description="User audio reading the option.")]
MCOptions = Annotated[str, Form(description="JSON-encoded list of option strings.")]
MCLang = Annotated[str, Form(description="BCP-47 or short code.")]


@router.post("/{story_id}/quiz/resolve-mc", response_model=MCResolveOut)
async def resolve_mc(
    story_id: UUID,
    db: DBSession,
    user: CurrentUser,
    settings: SettingsDep,
    locale: LocaleDep,
    audio: MCAudio,
    options: MCOptions,
    language: MCLang = "de-DE",
) -> MCResolveOut:
    """Transcribe user audio + fuzzy-match against MC options.

    `picked_index` is null when no option matches well enough; the UI
    asks the user to repeat. The transcript is always returned so the
    UI can surface "heard: «...»" if useful.
    """
    await _load_or_404(db, story_id, user.id, locale)

    if not settings.azure_speech_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=t("pron.unavailable", locale),
        )

    try:
        opts = json.loads(options)
        if not isinstance(opts, list) or not all(isinstance(o, str) for o in opts):
            raise ValueError
        if not opts or len(opts) > 8:
            raise ValueError
    except (ValueError, json.JSONDecodeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="options must be a JSON array of 1-8 strings",
        ) from e

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("pron.audio_empty", locale),
        )
    if len(audio_bytes) > settings.pronunciation_max_audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=t("pron.audio_too_large", locale),
        )

    bcp47 = _resolve_bcp47(language)

    try:
        wav_path: Path = await run_in_threadpool(transcode_to_wav, audio_bytes)
    except TranscodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("pron.audio_undecodable", locale),
        ) from None
    except FfmpegMissingError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=t("pron.unavailable", locale),
        ) from None

    try:
        transcript = await run_in_threadpool(
            transcribe,
            wav_path,
            bcp47,
            azure_key=settings.azure_speech_key or "",
            azure_region=settings.azure_speech_region,
        )
    except AzureSpeechError as e:
        if e.recoverable:
            # No speech detected — return empty transcript so the UI prompts
            # a retry without failing the request.
            return MCResolveOut(transcript="", picked_index=None, option_scores=[])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=t("pron.upstream_error", locale),
        ) from e
    finally:
        wav_path.unlink(missing_ok=True)

    picked, scores = resolve_option(transcript, opts)
    return MCResolveOut(transcript=transcript, picked_index=picked, option_scores=scores)


@router.post("/{story_id}/finish", response_model=StoryFinishOut)
async def finish_story(
    story_id: UUID, db: DBSession, user: CurrentUser, locale: LocaleDep
) -> StoryFinishOut:
    """The 'historia completada' event (fires when the reader reaches the
    Finish summary). Idempotent. Feeds the completar gate."""
    story = await _load_or_404(db, story_id, user.id, locale)
    view = (
        await db.execute(
            select(StoryView)
            .where(StoryView.story_id == story.id, StoryView.user_id == user.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if view is None:
        view = StoryView(story_id=story.id, user_id=user.id)
        db.add(view)
    if view.finished_at is None:
        view.finished_at = datetime.now(UTC)
    advanced = False
    if story.module_id is not None and story.module_id == user.current_module_id:
        await db.flush()  # the new view must be visible to the count
        advanced = await advance_module_if_completed(db, user=user)
    await db.commit()
    return StoryFinishOut(finished_at=view.finished_at, module_advanced=advanced)
