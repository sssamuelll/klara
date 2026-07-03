"""Build the curated seed story library (spec 2026-07-03 §8).

Usage:
    uv run python -m klara.scripts.build_story_library

Generates PER_MODULE stories per German A1 module for native_language=es using
the real generation pipeline (coverage-gated), inserts them as source='seed',
and pre-warms the global TTS audio cache. Idempotent: resume is topic-based —
only curated topics with no active seed entry for the (module, native) pair are
(re)generated, so a partial run picks up exactly the missing topics. Duplicate
content hashes are never inserted.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from klara.config import get_settings
from klara.curriculum.library import library_content_hash
from klara.curriculum.modules import module_target_lemmas
from klara.db import dispose_engine, get_sessionmaker, init_engine
from klara.llm.base import LLMClient
from klara.llm.litellm_impl import LiteLLMClient
from klara.models import Module, StoryLibrary
from klara.services.story_gen import generate_story_draft
from klara.services.tts_precache import collect_story_texts, precache_texts

log = structlog.get_logger(__name__)

PER_MODULE = 5
MAX_ATTEMPTS = 3

# Curated topics per module sequence_order. Each varies scene/protagonist so
# the module's stories don't read as clones (module-level substitute for the
# per-user recent-vocab dedup, spec §8).
TOPICS: dict[int, list[str]] = {
    1: [
        "pedir un café y un pastel",
        "una tarde de lluvia en el café",
        "el primer día de trabajo de una mesera",
        "dos amigos comparten una tarta",
        "un turista pide en alemán por primera vez",
    ],
    2: [
        "conocer a un vecino nuevo",
        "presentarse el primer día de clase",
        "un encuentro en el tren",
        "una llamada telefónica formal",
        "presentar a un amigo en una fiesta",
    ],
    3: [
        "una cena familiar de domingo",
        "mostrar fotos de la familia",
        "la visita de la abuela",
        "un hermano pequeño curioso",
        "planear un cumpleaños en familia",
    ],
    4: [
        "llegar tarde a una cita",
        "comprar entradas de cine",
        "preguntar la hora en la calle",
        "el horario del tren",
        "contar el dinero del mercado",
    ],
    5: [
        "comprar fruta en el mercado",
        "buscar un regalo",
        "una oferta en el supermercado",
        "devolver una camisa",
        "la lista de compras olvidada",
    ],
    6: [
        "mudanza a un apartamento nuevo",
        "buscar las llaves perdidas",
        "ordenar la sala",
        "una visita sorpresa",
        "arreglar la cocina",
    ],
    7: [
        "una mañana con prisa",
        "la rutina de un estudiante",
        "el desayuno perfecto",
        "una noche tranquila",
        "el despertador que no sonó",
    ],
    8: [
        "perderse en el U-Bahn",
        "preguntar por una dirección",
        "el autobús equivocado",
        "un paseo en bicicleta",
        "comprar un billete de tren",
    ],
}


def _module_objective(module: Module) -> str:
    can_dos = "; ".join(module.can_dos or [])
    focus = "; ".join(module.grammatical_focus or [])
    parts = ["OBJETIVO DEL MÓDULO (la historia debe servir este objetivo, sin forzar):"]
    if can_dos:
        parts.append(f"Can-do: {can_dos}.")
    if focus:
        parts.append(f"Foco gramatical: {focus}.")
    return " ".join(parts)


async def build_library(
    db: AsyncSession,
    llm: LLMClient,
    *,
    language: str,
    native: str,
    per_module: int,
    warm_audio: Callable[[list[str]], Awaitable[None]] | None = None,
    max_attempts: int = MAX_ATTEMPTS,
) -> int:
    modules = (
        (
            await db.execute(
                select(Module)
                .where(Module.language == language)
                .order_by(Module.sequence_order.asc())
            )
        )
        .scalars()
        .all()
    )
    inserted = 0
    for module in modules:
        topics = TOPICS.get(module.sequence_order, [])[:per_module]
        # Topic-based resume: positional resume (topics[have:]) misaligns after
        # a partial run — a mid-list failure would leave that topic forever
        # skipped while re-generating an already-seeded one. Diff against the
        # topics actually present instead.
        existing_topics = set(
            (
                await db.execute(
                    select(StoryLibrary.topic).where(
                        StoryLibrary.module_id == module.id,
                        StoryLibrary.native_language == native,
                        StoryLibrary.is_active.is_(True),
                        StoryLibrary.source == "seed",
                    )
                )
            ).scalars()
        )
        have = len(existing_topics)
        if have >= per_module:
            log.info("library.build.skip_full", module=module.title, have=have)
            continue
        lemmas = await module_target_lemmas(db, module)
        objective = _module_objective(module)
        for topic in [t for t in topics if t not in existing_topics]:
            draft = None
            for attempt in range(max_attempts):
                try:
                    candidate = await generate_story_draft(
                        db,
                        llm,
                        level=module.cefr_level,
                        target_language=language,
                        native_language=native,
                        learning_context=None,
                        topic=topic,
                        model=None,
                        target_lemmas=lemmas,
                        module_objective=objective,
                        avoid_lemmas=[],
                    )
                except Exception as exc:
                    # Broad on purpose: a litellm provider/network error is as
                    # much a "this attempt failed" signal as StoryGenerationError
                    # — narrowing to the latter aborted the whole run on the
                    # first transient provider hiccup.
                    log.warning(
                        "library.build.gen_failed", topic=topic, attempt=attempt, error=str(exc)
                    )
                    continue
                if candidate.dropped_lemmas:
                    log.info(
                        "library.build.coverage_retry",
                        topic=topic,
                        attempt=attempt,
                        dropped=candidate.dropped_lemmas,
                    )
                    continue
                draft = candidate
                break
            if draft is None:
                log.warning("library.build.skipped", module=module.title, topic=topic)
                continue
            h = library_content_hash(draft.content)
            dup = (
                await db.execute(select(StoryLibrary.id).where(StoryLibrary.content_hash == h))
            ).first()
            if dup is not None:
                log.info("library.build.dup_hash", topic=topic)
                continue
            db.add(
                StoryLibrary(
                    module_id=module.id,
                    language=language,
                    native_language=native,
                    level=module.cefr_level,
                    title=draft.title,
                    content=draft.content,
                    target_vocab_item_ids=[w.id for w in draft.target_words],
                    quiz_items=draft.quiz_items,
                    insight_title=draft.insight_title,
                    insight_body=draft.insight_body,
                    topic=topic,
                    source="seed",
                    content_hash=h,
                    generated_by_provider=draft.provider,
                    generated_by_model=draft.model,
                    generation_cost_usd=draft.cost_usd,
                )
            )
            await db.flush()
            inserted += 1
            # Commit first so audio warming can never lose a paid generation:
            # a mid-run crash (or a later exhausted-retry topic) keeps every
            # already-committed row, and topic-based resume above has
            # committed state to resume from.
            await db.commit()
            log.info(
                "library.build.inserted", module=module.title, topic=topic, cost=draft.cost_usd
            )
            if warm_audio is not None:
                words = [
                    {"lemma": w.lemma, "example_target": w.example_target}
                    for w in draft.target_words
                ]
                texts = collect_story_texts(draft.content, words)
                if draft.title:
                    texts = [draft.title] + [t for t in texts if t != draft.title]
                try:
                    await warm_audio(texts)
                except Exception as exc:
                    log.warning("library.build.warm_failed", topic=topic, error=str(exc))
    return inserted


async def _run() -> None:
    settings = get_settings()
    init_engine(settings)
    try:
        llm = LiteLLMClient(
            settings,
            default_model=settings.llm_story_model,
            default_extra_body=settings.llm_story_extra_body,
        )

        async def warm(texts: list[str]) -> None:
            await precache_texts(settings, texts, "de")

        sessionmaker = get_sessionmaker()
        async with sessionmaker() as db:
            # build_library commits per inserted row — nothing left to commit here.
            n = await build_library(
                db, llm, language="de", native="es", per_module=PER_MODULE, warm_audio=warm
            )
        print(f"Insertadas {n} historia(s) en la librería.")
    finally:
        await dispose_engine()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
