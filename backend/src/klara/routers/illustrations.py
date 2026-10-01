"""GET /illustrations/{hash}: la portada de una historia, sin sesión.

Pública a propósito, como /tts: el <img> de la app nativa no manda el Bearer.
El hash (sha256 de la escena con su versión de estilo) no se puede adivinar sin
conocer la escena, y las escenas no llevan nombres ni personas reconocibles."""

import re

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import select

from klara.dependencies import DBSession
from klara.models import Illustration

router = APIRouter(prefix="/illustrations", tags=["illustrations"])

_HASH = re.compile(r"^[0-9a-f]{64}$")
# Lista cerrada: los bytes vienen de una API externa y la ruta es pública. `image/*`
# no basta, porque un image/svg+xml abierto directo ejecuta script en nuestro origen.
_IMAGE_TYPES = frozenset({"image/png", "image/jpeg", "image/webp"})


@router.get("/{hash_}")
async def get_illustration(hash_: str, db: DBSession) -> Response:
    if not _HASH.match(hash_):
        raise HTTPException(status_code=404, detail="illustration.not_found")
    row = (
        await db.execute(
            select(Illustration.image_data, Illustration.mime_type).where(
                Illustration.hash == hash_
            )
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="illustration.not_found")
    media = row.mime_type if row.mime_type in _IMAGE_TYPES else "application/octet-stream"
    return Response(
        content=row.image_data,
        media_type=media,
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": f'"{hash_}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
