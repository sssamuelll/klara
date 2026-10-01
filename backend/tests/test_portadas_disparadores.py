"""Cuándo se dibuja la ilustración (spec §3.4): en segundo plano al crear una
historia con escena, y en build_story_library después de guardar cada entrada."""

from __future__ import annotations

import base64
import json

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import func, select, text

from klara.config import get_settings
from klara.curriculum.modules import load_modules
from klara.dependencies import get_story_llm
from klara.llm.base import LLMResponse
from klara.models import Illustration, StoryLibrary
from klara.scripts.build_story_library import build_library
from klara.services.illustration import ensure_illustration


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


@pytest_asyncio.fixture
async def app_con_llm():
    """App real con la LLM de historias reemplazada (como test_create_story_module)."""
    from klara.config import get_settings
    from klara.db import dispose_engine, init_engine
    from klara.main import create_app

    init_engine(get_settings())
    app = create_app()
    clientes: list[AsyncClient] = []

    def hacer(content: str) -> AsyncClient:
        app.dependency_overrides[get_story_llm] = lambda: FakeLLM(content)
        cliente = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        clientes.append(cliente)
        return cliente

    yield hacer
    for cliente in clientes:
        await cliente.aclose()
    await dispose_engine()


async def _login(client, seed_invite, email: str) -> str:
    token = await seed_invite(email=None)
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "hunter2hunter2", "invite_token": token},
    )
    assert r.status_code == 201, r.text
    r2 = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": email, "password": "hunter2hunter2"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r2.status_code == 204, r2.text
    return r2.headers["set-cookie"].split(";")[0]


async def _seed_modulo(db) -> None:
    await load_modules(
        db,
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
    await db.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "extra, esperadas",
    [
        ({"scene": "A café at noon."}, ["A café at noon."]),
        ({}, []),
    ],
    ids=["con-escena", "sin-escena"],
)
async def test_crear_historia_agenda_la_ilustracion_solo_con_escena(
    app_con_llm, seed_invite, monkeypatch, extra, esperadas
):
    llamadas: list[str] = []

    async def fake(settings, scene):
        llamadas.append(scene)

    monkeypatch.setattr("klara.routers.stories.illustrate_in_background", fake)
    client = app_con_llm(_json(**extra))
    cookie = await _login(client, seed_invite, f"crear-{len(esperadas)}@example.com")
    resp = await client.post(
        "/api/v1/stories",
        json={"topic": "café", "topic_origin": "free"},
        headers={"Cookie": cookie},
    )
    assert resp.status_code == 201, resp.text
    assert llamadas == esperadas


@pytest.mark.asyncio
async def test_build_ilustra_despues_de_guardar(db_session):
    await _seed_modulo(db_session)
    vistas: list[tuple[str, int]] = []

    async def ilustrar(db, scene):
        n = (await db.execute(select(func.count()).select_from(StoryLibrary))).scalar_one()
        vistas.append((scene, n))  # la fila ya está guardada cuando se ilustra
        return "h" * 64

    n = await build_library(
        db_session,
        FakeLLM(_json(scene="A café at noon.")),
        language="de",
        native="es",
        per_module=1,
        illustrate=ilustrar,
    )
    assert n == 1
    assert vistas == [("A café at noon.", 1)]


@pytest.mark.asyncio
async def test_build_sobrevive_a_una_ilustracion_que_falla(db_session):
    await _seed_modulo(db_session)

    async def rota(db, scene):
        raise RuntimeError("gemini caído")

    n = await build_library(
        db_session,
        FakeLLM(_json(scene="A café at noon.")),
        language="de",
        native="es",
        per_module=1,
        illustrate=rota,
    )
    assert n == 1
    count = (await db_session.execute(select(func.count()).select_from(StoryLibrary))).scalar_one()
    assert count == 1


class FakeLLMDistinto(FakeLLM):
    """Una historia distinta por llamada, para que los hashes de contenido no choquen."""

    def __init__(self) -> None:
        super().__init__("")
        self.llamadas = 0

    async def complete(self, **kwargs):
        self.llamadas += 1
        self.content = _json(
            sentences=[
                {
                    "target": f"Der Kaffee Nummer {self.llamadas} ist heiß.",
                    "native": "x",
                    "new_words": ["Kaffee"],
                    "breakdown": [{"word": "Kaffee", "translation": "café"}],
                }
            ],
            scene=f"A café at noon, table {self.llamadas}.",
        )
        return await super().complete(**kwargs)


@pytest.mark.asyncio
async def test_build_sigue_con_el_tema_siguiente_si_la_ilustracion_rompe_la_base(db_session):
    """ensure_illustration abre con un SELECT, así que puede fallar con la transacción ya
    empezada (p. ej. un mime_type más largo que su columna). Deshacer esa transacción
    entera vencería los objetos que el build sigue recorriendo: MissingGreenlet en el tema
    siguiente. La ilustración va en un savepoint y el tema siguiente se construye igual."""
    await _seed_modulo(db_session)
    escenas: list[str] = []

    async def rota_en_la_base(db, scene):
        escenas.append(scene)
        if len(escenas) == 1:
            await db.execute(text("SELECT 1/0"))  # error de la base: aborta la transacción
        return "h" * 64

    n = await build_library(
        db_session,
        FakeLLMDistinto(),
        language="de",
        native="es",
        per_module=2,
        illustrate=rota_en_la_base,
    )
    assert n == 2
    assert len(escenas) == 2


@pytest.mark.asyncio
async def test_build_confirma_la_ilustracion_que_dibuja_el_servicio(db_session, db_engine):
    """Con ensure_illustration de verdad (Gemini falso), la imagen queda confirmada: la ve
    otra conexión, que solo lee lo commiteado. Es el cableado de _run."""
    await _seed_modulo(db_session)
    pedidas: list[httpx.Request] = []

    def gemini(request: httpx.Request) -> httpx.Response:
        pedidas.append(request)
        parte = {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(b"png").decode()}}
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [parte]}}]})

    settings = get_settings().model_copy(update={"gemini_api_key": SecretStr("k")})

    async def ilustrar(db, scene):
        async with httpx.AsyncClient(transport=httpx.MockTransport(gemini)) as client:
            return await ensure_illustration(db, scene, settings=settings, client=client)

    await build_library(
        db_session,
        FakeLLM(_json(scene="A café at noon.")),
        language="de",
        native="es",
        per_module=1,
        illustrate=ilustrar,
    )
    async with db_engine.connect() as otra:
        escenas = (await otra.execute(select(Illustration.scene))).scalars().all()
    assert escenas == ["A café at noon."]
    assert len(pedidas) == 1
