"""Subtítulo y escena en el flujo de historias (spec §3.1): el modelo los devuelve,
el borrador los limpia y recorta, y viajan a la historia, a la biblioteca (build y
reciclaje) y a la copia al reclamar."""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import select

from klara.curriculum.library import claim_library_entry, maybe_recycle_to_library
from klara.curriculum.modules import load_modules
from klara.llm.base import LLMResponse
from klara.llm.prompts import build_story_system_prompt
from klara.models import Module, Story, StoryLibrary, User
from klara.models.enums import CEFRLevel
from klara.scripts.build_story_library import build_library
from klara.services.story_gen import SCENE_MAX, SUBTITLE_MAX, generate_story, generate_story_draft


def _json(**extra) -> str:
    return json.dumps(
        {
            "title": "Der Kaffee",
            "sentences": [
                {
                    "target": "Der Kaffee ist heiß.",
                    "native": "El café está caliente.",
                    "new_words": ["Kaffee"],
                    "breakdown": [{"word": "Kaffee", "translation": "café"}],
                }
            ],
            "comprehension_questions": [],
            "target_words": [
                {"lemma": "Kaffee", "pos": "noun", "gender": "der", "translation": "café"}
            ],
            "quiz_items": None,
            **extra,
        }
    )


class FakeLLM:
    def __init__(self, content: str) -> None:
        self.content = content

    async def complete(
        self, *, messages, model=None, max_tokens=1024, temperature=0.7, response_format=None
    ):
        return LLMResponse(content=self.content, model="fake", provider="fake", cost_usd=0.001)

    async def stream(self, *, messages, model=None, max_tokens=1024, temperature=0.7):
        raise NotImplementedError


async def _draft(db, content: str):
    return await generate_story_draft(
        db,
        FakeLLM(content),
        level=CEFRLevel.A1,
        target_language="de",
        native_language="es",
        learning_context=None,
        topic=None,
        model=None,
    )


async def _usuario_y_modulo(db):
    user = User(
        id=uuid.uuid4(),
        email=None,
        hashed_password=None,
        is_active=True,
        is_verified=False,
        is_superuser=False,
        display_name="Ana",
        level=CEFRLevel.A1,
        native_language="es",
        target_language="de",
    )
    module = Module(
        id=uuid.uuid4(),
        language="de",
        cefr_level=CEFRLevel.A1,
        sequence_order=1,
        title="En el café",
        can_dos=[],
        grammatical_focus=[],
    )
    db.add_all([user, module])
    await db.flush()
    return user, module


def test_el_prompt_pide_subtitulo_y_escena():
    prompt = build_story_system_prompt(
        target_label="alemán",
        native_label="español",
        level="A2",
        target_language="de",
        learning_context=None,
    )
    assert '"subtitle"' in prompt and '"scene"' in prompt
    assert "{native_label}" not in prompt


@pytest.mark.asyncio
async def test_el_borrador_limpia_y_recorta(db_session):
    draft = await _draft(
        db_session, _json(subtitle="  Una panadería,\n un sábado  ", scene="x" * 900)
    )
    assert draft.subtitle == "Una panadería, un sábado"
    assert draft.scene == "x" * SCENE_MAX
    largo = await _draft(db_session, _json(subtitle="y" * 400, scene="A bakery."))
    assert largo.subtitle == "y" * SUBTITLE_MAX


@pytest.mark.asyncio
async def test_sin_campos_o_raros_quedan_en_none(db_session):
    draft = await _draft(db_session, _json())
    assert (draft.subtitle, draft.scene) == (None, None)
    raros = await _draft(db_session, _json(subtitle=42, scene="   "))
    assert (raros.subtitle, raros.scene) == (None, None)


@pytest.mark.asyncio
async def test_la_historia_generada_los_guarda(db_session):
    user, _ = await _usuario_y_modulo(db_session)
    result = await generate_story(
        db_session,
        FakeLLM(_json(subtitle="Un café.", scene="A café at noon.")),
        user_id=user.id,
        level=CEFRLevel.A1,
        target_language="de",
        native_language="es",
        learning_context=None,
        topic=None,
        model=None,
    )
    assert (result.story.subtitle, result.story.scene) == ("Un café.", "A café at noon.")


@pytest.mark.asyncio
async def test_reclamar_copia_subtitulo_y_escena(db_session):
    user, module = await _usuario_y_modulo(db_session)
    entry = StoryLibrary(
        module_id=module.id,
        language="de",
        native_language="es",
        level=CEFRLevel.A1,
        title="Der Kaffee",
        content={"sentences": []},
        target_vocab_item_ids=[],
        source="seed",
        content_hash="f" * 64,
        subtitle="Un café.",
        scene="A café at noon.",
    )
    db_session.add(entry)
    await db_session.flush()
    story = await claim_library_entry(db_session, user=user, entry=entry, module=module)
    assert (story.subtitle, story.scene) == ("Un café.", "A café at noon.")


@pytest.mark.asyncio
async def test_reciclar_copia_subtitulo_y_escena(db_session):
    user, module = await _usuario_y_modulo(db_session)
    story = Story(
        user_id=user.id,
        level=CEFRLevel.A1,
        target_language="de",
        native_language="es",
        title="Der Kaffee",
        content={"sentences": [{"target": "Der Kaffee ist heiß."}]},
        target_vocab_item_ids=[],
        module_id=module.id,
        subtitle="Un café.",
        scene="A café at noon.",
    )
    db_session.add(story)
    await db_session.flush()
    await maybe_recycle_to_library(
        db_session, story=story, dropped_lemmas=[], topic=None, topic_origin="none"
    )
    entry = (await db_session.execute(select(StoryLibrary))).scalar_one()
    assert (entry.subtitle, entry.scene) == ("Un café.", "A café at noon.")


@pytest.mark.asyncio
async def test_build_guarda_subtitulo_y_escena(db_session):
    await load_modules(
        db_session,
        language="de",
        modules=[
            {
                "sequence_order": 1,
                "title": "En el café",
                "cefr_level": "A1",
                "can_dos": ["pedir"],
                "grammatical_focus": ["género"],
                "vocab": [
                    {
                        "lemma": "Kaffee",
                        "pos": "noun",
                        "gender": "der",
                        "translations": {"es": "café"},
                    }
                ],
            }
        ],
    )
    await db_session.commit()
    n = await build_library(
        db_session,
        FakeLLM(_json(subtitle="Un café.", scene="A café at noon.")),
        language="de",
        native="es",
        per_module=1,
    )
    assert n == 1
    entry = (await db_session.execute(select(StoryLibrary))).scalar_one()
    assert (entry.subtitle, entry.scene) == ("Un café.", "A café at noon.")
