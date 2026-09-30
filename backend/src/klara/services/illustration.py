"""La portada de una historia: una ilustración por escena, en caché (spec §3).

La clave es sha256("{STYLE_VERSION}|{escena normalizada}"). El modelo se guarda
pero no entra en la clave: si Google retira el preview y cambiamos de modelo,
las imágenes hechas siguen sirviendo. Cambiar el estilo es intencional: se sube
STYLE_VERSION y el backfill regenera.
"""

from __future__ import annotations

import base64
import hashlib

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from klara.config import Settings
from klara.db import get_sessionmaker
from klara.models import Illustration

log = structlog.get_logger(__name__)

STYLE_VERSION = 1
# El estilo cálido que eligió Samuel el 2026-09-30 (la prueba de 3.1 Flash de la
# galería). Se describe entero a propósito: no se deja a que el modelo desobedezca.
STYLE_PROMPT = (
    "Editorial illustration for a short story in a language-learning app, in the look of a "
    "hand-pulled risograph or linocut print on cream paper (#F4EFE6). Warm palette led by warm "
    "black ink (#1A1814) and vermilion (#CB4644), with amber window light, soft pinks and stone "
    "greys. Visible print grain and slight misregistration, flat shapes, confident hand-cut "
    "lines. Wide banner composition with some open paper around the subject. No text, no "
    "letters, no words on signs, no logos, no recognizable people."
)
MAX_BYTES = 3 * 1024 * 1024
COST_PER_IMAGE_USD = 0.069  # medido con la cabecera de costo de LiteLLM, 2026-09-30
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def normalize_scene(scene: str | None) -> str:
    return " ".join((scene or "").split())


def illustration_hash(scene: str) -> str:
    return hashlib.sha256(f"{STYLE_VERSION}|{normalize_scene(scene)}".encode()).hexdigest()


def illustration_path(hash_: str) -> str:
    return f"/illustrations/{hash_}"


def build_prompt(scene: str) -> str:
    return f"{STYLE_PROMPT}\nScene: {normalize_scene(scene)}"


async def _generate(settings: Settings, scene: str, client: httpx.AsyncClient) -> tuple[bytes, str]:
    assert settings.gemini_api_key is not None  # lo comprueba ensure_illustration
    resp = await client.post(
        GEMINI_URL.format(model=settings.illustration_model),
        headers={"x-goog-api-key": settings.gemini_api_key.get_secret_value()},
        json={
            "contents": [{"parts": [{"text": build_prompt(scene)}]}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {"aspectRatio": "21:9", "imageSize": "1K"},
            },
        },
        timeout=60.0,
    )
    resp.raise_for_status()
    for candidate in resp.json().get("candidates") or []:
        for part in (candidate.get("content") or {}).get("parts") or []:
            data = part.get("inlineData") or part.get("inline_data")
            if data and data.get("data"):
                mime = data.get("mimeType") or data.get("mime_type") or "image/jpeg"
                return base64.b64decode(data["data"]), mime
    raise ValueError("gemini: la respuesta no trae imagen")


async def ensure_illustration(
    db: AsyncSession,
    scene: str | None,
    *,
    settings: Settings,
    client: httpx.AsyncClient | None = None,
) -> str | None:
    """El hash de la ilustración de `scene`, generándola si hace falta.

    None si la escena está vacía, si no hay clave o si Gemini falla. Nunca
    lanza por la red. No hace commit: lo hace quien la llama."""
    escena = normalize_scene(scene)
    if not escena:
        return None
    h = illustration_hash(escena)
    if (await db.execute(select(Illustration.hash).where(Illustration.hash == h))).first():
        return h
    if settings.gemini_api_key is None:
        return None
    http = client or httpx.AsyncClient()
    try:
        raw, mime = await _generate(settings, escena, http)
    except Exception as exc:  # red, HTTP, bloqueo de seguridad o respuesta sin imagen
        log.warning("illustration.generate_failed", hash=h, error=str(exc))
        return None
    finally:
        if client is None:
            await http.aclose()
    if len(raw) > MAX_BYTES:
        log.warning("illustration.too_big", hash=h, size=len(raw))
        return None
    await db.execute(
        insert(Illustration)
        .values(
            hash=h,
            scene=escena,
            style_version=STYLE_VERSION,
            model=settings.illustration_model,
            mime_type=mime,
            image_data=raw,
            size_bytes=len(raw),
        )
        .on_conflict_do_nothing(index_elements=["hash"])
    )
    return h


async def illustrate_in_background(settings: Settings, scene: str | None) -> None:
    """Tarea de fondo tras crear una historia: abre su propia sesión y nunca lanza."""
    try:
        sessionmaker = get_sessionmaker()
    except RuntimeError:
        log.warning("illustration.no_db")
        return
    try:
        async with sessionmaker() as db:
            if await ensure_illustration(db, scene, settings=settings):
                await db.commit()
    except Exception as exc:
        log.warning("illustration.background_failed", error=str(exc))
