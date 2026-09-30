"""Backfill de portadas: subtítulo, escena e ilustración para lo que ya existe.

En la caja:
    docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend \
        python -m klara.scripts.backfill_portadas --dry-run
    ... y sin --dry-run para gastar de verdad (--limit N, --only-library).

Fase 1, textos. Las entradas de la biblioteca sin subtítulo o escena se los
piden a la LLM de historias. Las historias clonadas los copian de su entrada,
sin LLM. Las historias propias sin textos hacen la misma llamada que la
biblioteca. Fase 2, imágenes: cada escena distinta sin fila pasa por
ensure_illustration, de a una. Se puede volver a correr: salta lo que ya está.
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from klara.config import Settings, get_settings
from klara.db import dispose_engine, get_sessionmaker, init_engine
from klara.i18n import language_label
from klara.llm.base import LLMClient, Message
from klara.llm.litellm_impl import LiteLLMClient
from klara.models import Illustration, Story, StoryLibrary
from klara.services.illustration import (
    COST_PER_IMAGE_USD,
    ensure_illustration,
    illustration_hash,
    normalize_scene,
)
from klara.services.story_gen import SCENE_MAX, SUBTITLE_MAX, _extract_json, trim_text

log = structlog.get_logger(__name__)

PORTADA_PROMPT = """Te paso una micro-historia en {target_label} con su traducción al {native_label}.
Devuelve SOLO JSON válido con este esquema, sin texto extra:
{{
  "subtitle": "una línea en {native_label}, 70 caracteres o menos, que diga de qué va la escena sin contar el final",
  "scene": "la escena principal descrita EN INGLÉS para un ilustrador, 300 caracteres o menos: lugar, momento del día, objetos y luz. Sin texto, letreros, marcas ni personas reconocibles"
}}

Título: {title}
Historia:
{sentences}"""

Illustrate = Callable[..., Awaitable[str | None]]


async def portada_texts(
    llm: LLMClient, *, title: str, content: dict, target_language: str, native_language: str
) -> tuple[str | None, str | None]:
    sentences = "\n".join(
        f"- {s.get('target', '')} ({s.get('native', '')})" for s in content.get("sentences") or []
    )
    prompt = PORTADA_PROMPT.format(
        target_label=language_label(target_language),
        native_label=language_label(native_language),
        title=title,
        sentences=sentences,
    )
    resp = await llm.complete(
        messages=[Message("user", prompt)],
        max_tokens=400,
        temperature=0.4,
        response_format={"type": "json_object"},
    )
    data: dict[str, Any] = _extract_json(resp.content)
    return trim_text(data.get("subtitle"), SUBTITLE_MAX), trim_text(data.get("scene"), SCENE_MAX)


async def _textos(db: AsyncSession, llm: LLMClient, filas, *, dry_run: bool, stats: dict) -> int:
    hechos = 0
    for fila in filas:
        if dry_run:
            hechos += 1
            continue
        target = fila.target_language if isinstance(fila, Story) else fila.language
        try:
            sub, scene = await portada_texts(
                llm,
                title=fila.title,
                content=fila.content or {},
                target_language=target,
                native_language=fila.native_language,
            )
        except Exception as exc:
            log.warning("backfill.texts_failed", id=str(fila.id), error=str(exc))
            stats["failed"] += 1
            continue
        if scene is None:
            stats["failed"] += 1
            continue
        fila.subtitle = fila.subtitle or sub
        fila.scene = fila.scene or scene
        await db.commit()
        hechos += 1
    return hechos


async def backfill(
    db: AsyncSession,
    llm: LLMClient,
    *,
    settings: Settings,
    dry_run: bool,
    limit: int | None,
    only_library: bool,
    illustrate: Illustrate = ensure_illustration,
) -> dict[str, int]:
    stats = {
        "library_texts": 0,
        "cloned_texts": 0,
        "own_texts": 0,
        "images": 0,
        "images_max": 0,
        "failed": 0,
    }
    sin_textos = or_(StoryLibrary.subtitle.is_(None), StoryLibrary.scene.is_(None))
    entradas = (
        (
            await db.execute(
                select(StoryLibrary)
                .where(sin_textos)
                .order_by(StoryLibrary.created_at)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    stats["library_texts"] = await _textos(db, llm, entradas, dry_run=dry_run, stats=stats)

    if not only_library:
        if not dry_run:
            clones = (
                await db.execute(
                    select(Story, StoryLibrary)
                    .join(StoryLibrary, Story.library_source_id == StoryLibrary.id)
                    .where(
                        or_(Story.subtitle.is_(None), Story.scene.is_(None)),
                        StoryLibrary.scene.is_not(None),
                    )
                )
            ).all()
            for story, entry in clones:
                story.subtitle = story.subtitle or entry.subtitle
                story.scene = story.scene or entry.scene
                stats["cloned_texts"] += 1
            await db.commit()
        propias = (
            (
                await db.execute(
                    select(Story)
                    .where(
                        Story.library_source_id.is_(None),
                        or_(Story.subtitle.is_(None), Story.scene.is_(None)),
                    )
                    .order_by(Story.created_at)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        stats["own_texts"] = await _textos(db, llm, propias, dry_run=dry_run, stats=stats)

    escenas = [
        s
        for (s,) in (
            await db.execute(select(StoryLibrary.scene).where(StoryLibrary.scene.is_not(None)))
        ).all()
    ]
    if not only_library:
        escenas += [
            s
            for (s,) in (
                await db.execute(select(Story.scene).where(Story.scene.is_not(None)))
            ).all()
        ]
    hechas = set((await db.execute(select(Illustration.hash))).scalars().all())
    unicas = {normalize_scene(s) for s in escenas} - {""}
    faltan = sorted(s for s in unicas if illustration_hash(s) not in hechas)
    if limit is not None:
        faltan = faltan[:limit]
    if dry_run:
        # Techo: las escenas sin imagen que ya existen, más una por cada texto que
        # se generaría. Los clones comparten la escena de su entrada y no suman.
        stats["images_max"] = len(faltan) + stats["library_texts"] + stats["own_texts"]
        return stats
    for escena in faltan:
        if await illustrate(db, escena, settings=settings):
            await db.commit()
            stats["images"] += 1
        else:
            stats["failed"] += 1
    return stats


def _informe(stats: dict[str, int], *, dry_run: bool) -> str:
    textos = stats["library_texts"] + stats["own_texts"]
    if dry_run:
        return (
            f"En seco. Textos a generar: {textos} (biblioteca {stats['library_texts']}, "
            f"propias {stats['own_texts']}); centavos en DeepSeek.\n"
            f"Imágenes: como mucho {stats['images_max']} × ${COST_PER_IMAGE_USD} = "
            f"${stats['images_max'] * COST_PER_IMAGE_USD:.2f}."
        )
    return (
        f"Textos: {textos} generados y {stats['cloned_texts']} copiados de su entrada. "
        f"Imágenes: {stats['images']} (~ ${stats['images'] * COST_PER_IMAGE_USD:.2f}). "
        f"Fallos: {stats['failed']} (se puede volver a correr)."
    )


async def _run(args: argparse.Namespace) -> None:
    settings = get_settings()
    init_engine(settings)
    try:
        llm = LiteLLMClient(
            settings,
            default_model=settings.llm_story_model,
            default_extra_body=settings.llm_story_extra_body,
        )
        async with get_sessionmaker()() as db:
            stats = await backfill(
                db,
                llm,
                settings=settings,
                dry_run=args.dry_run,
                limit=args.limit,
                only_library=args.only_library,
            )
        print(_informe(stats, dry_run=args.dry_run))
    finally:
        await dispose_engine()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill de subtítulos, escenas e ilustraciones.")
    parser.add_argument(
        "--dry-run", action="store_true", help="contar y estimar, sin escribir ni llamar"
    )
    parser.add_argument("--limit", type=int, default=None, help="tope por fase")
    parser.add_argument("--only-library", action="store_true", help="solo la biblioteca")
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
