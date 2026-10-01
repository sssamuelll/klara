"""services/illustration.py (spec §3.3): una imagen por escena, en caché, sin
reintentos y sin lanzar nunca hacia quien la pide."""

from __future__ import annotations

import base64
import json

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from klara.config import get_settings
from klara.models import Illustration
from klara.services import illustration as ilus

ESCENA = "A small half-timbered bakery at dawn, a bicycle by the door."
JPEG = b"\xff\xd8\xff\xe0fake-jpeg"


def _settings(key: str | None = "k"):
    return get_settings().model_copy(
        update={
            "gemini_api_key": SecretStr(key) if key else None,
            "illustration_model": "gemini-3.1-flash-image-preview",
        }
    )


class Gemini:
    """Transporte falso: cuenta las llamadas y responde lo que se le pida."""

    def __init__(self, response: httpx.Response | None = None) -> None:
        self.calls: list[httpx.Request] = []
        self.response = response or httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "mimeType": "image/jpeg",
                                        "data": base64.b64encode(JPEG).decode(),
                                    }
                                }
                            ]
                        }
                    }
                ]
            },
        )

    def client(self) -> httpx.AsyncClient:
        def handler(request: httpx.Request) -> httpx.Response:
            self.calls.append(request)
            return self.response

        return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def _cuantas(db) -> int:
    return (await db.execute(select(func.count()).select_from(Illustration))).scalar_one()


def test_hash_normaliza_la_escena():
    a = ilus.illustration_hash("  A small   bakery\n at dawn ")
    assert a == ilus.illustration_hash("A small bakery at dawn")
    assert len(a) == 64


def test_hash_cambia_con_la_version_de_estilo(monkeypatch):
    antes = ilus.illustration_hash(ESCENA)
    monkeypatch.setattr(ilus, "STYLE_VERSION", ilus.STYLE_VERSION + 1)
    assert ilus.illustration_hash(ESCENA) != antes


@pytest.mark.asyncio
async def test_escena_vacia_no_llama(db_session):
    gemini = Gemini()
    h = await ilus.ensure_illustration(
        db_session, "   ", settings=_settings(), client=gemini.client()
    )
    assert h is None and gemini.calls == []


@pytest.mark.asyncio
async def test_sin_clave_no_llama(db_session):
    gemini = Gemini()
    h = await ilus.ensure_illustration(
        db_session, ESCENA, settings=_settings(None), client=gemini.client()
    )
    assert h is None and gemini.calls == []


@pytest.mark.asyncio
async def test_genera_guarda_y_despues_sale_de_cache(db_session):
    gemini = Gemini()
    h = await ilus.ensure_illustration(
        db_session, ESCENA, settings=_settings(), client=gemini.client()
    )
    await db_session.commit()
    assert h == ilus.illustration_hash(ESCENA)
    fila = (await db_session.execute(select(Illustration))).scalar_one()
    assert (fila.mime_type, fila.image_data, fila.size_bytes) == ("image/jpeg", JPEG, len(JPEG))
    assert (fila.style_version, fila.model) == (
        ilus.STYLE_VERSION,
        "gemini-3.1-flash-image-preview",
    )

    pedido = gemini.calls[0]
    cuerpo = json.loads(pedido.content)
    assert pedido.headers["x-goog-api-key"] == "k"
    assert "gemini-3.1-flash-image-preview:generateContent" in str(pedido.url)
    assert cuerpo["generationConfig"]["responseModalities"] == ["IMAGE"]
    assert cuerpo["generationConfig"]["imageConfig"] == {"aspectRatio": "21:9", "imageSize": "1K"}
    assert ESCENA in cuerpo["contents"][0]["parts"][0]["text"]

    otra = await ilus.ensure_illustration(
        db_session, ESCENA, settings=_settings(), client=gemini.client()
    )
    assert otra == h and len(gemini.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "respuesta",
    [
        httpx.Response(500, json={"error": "boom"}),
        httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "no image"}]}}]}),
        httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}}),
    ],
    ids=["http-500", "sin-imagen", "bloqueo"],
)
async def test_fallos_devuelven_none_y_no_guardan(db_session, respuesta):
    h = await ilus.ensure_illustration(
        db_session, ESCENA, settings=_settings(), client=Gemini(respuesta).client()
    )
    assert h is None
    assert await _cuantas(db_session) == 0


@pytest.mark.asyncio
async def test_imagen_demasiado_grande(db_session, monkeypatch):
    monkeypatch.setattr(ilus, "MAX_BYTES", 4)
    h = await ilus.ensure_illustration(
        db_session, ESCENA, settings=_settings(), client=Gemini().client()
    )
    assert h is None
    assert await _cuantas(db_session) == 0


@pytest.mark.asyncio
async def test_choque_de_insercion_devuelve_el_hash(db_session, db_engine, monkeypatch):
    """Otra petición guarda la misma escena entre la consulta y el INSERT."""
    real = ilus._generate

    async def generar_y_colarse(settings, scene, client):
        async with async_sessionmaker(db_engine)() as otra:
            otra.add(
                Illustration(
                    hash=ilus.illustration_hash(scene),
                    scene=scene,
                    style_version=ilus.STYLE_VERSION,
                    model="otra",
                    mime_type="image/png",
                    image_data=b"x",
                    size_bytes=1,
                )
            )
            await otra.commit()
        return await real(settings, scene, client)

    monkeypatch.setattr(ilus, "_generate", generar_y_colarse)
    h = await ilus.ensure_illustration(
        db_session, ESCENA, settings=_settings(), client=Gemini().client()
    )
    await db_session.commit()
    assert h == ilus.illustration_hash(ESCENA)
    assert await _cuantas(db_session) == 1


@pytest.mark.asyncio
async def test_el_fallo_se_loguea_con_su_tipo(db_session):
    """Un timeout trae str(exc) == "": sin el tipo, el log de la primera corrida pagada queda
    en `error=''` y no dice qué pasó."""
    from structlog.testing import capture_logs

    def se_agota(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("")

    cliente = httpx.AsyncClient(transport=httpx.MockTransport(se_agota))
    with capture_logs() as logs:
        h = await ilus.ensure_illustration(db_session, ESCENA, settings=_settings(), client=cliente)
    assert h is None
    (linea,) = [x for x in logs if x["event"] == "illustration.generate_failed"]
    assert linea["error"].startswith("ReadTimeout")


@pytest.mark.asyncio
async def test_el_fallo_en_segundo_plano_se_loguea_con_su_tipo(monkeypatch):
    from structlog.testing import capture_logs

    class SesionQueSeAgota:
        async def __aenter__(self):
            raise TimeoutError

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(ilus, "get_sessionmaker", lambda: SesionQueSeAgota)
    with capture_logs() as logs:
        await ilus.illustrate_in_background(_settings(), ESCENA)  # no lanza
    (linea,) = [x for x in logs if x["event"] == "illustration.background_failed"]
    assert linea["error"].startswith("TimeoutError")


@pytest.mark.asyncio
async def test_en_segundo_plano_sin_base_no_lanza():
    from klara.db import dispose_engine

    await dispose_engine()
    await ilus.illustrate_in_background(_settings(), ESCENA)
