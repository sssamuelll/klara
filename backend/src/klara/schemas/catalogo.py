"""Lo que entra y sale de las rutas del catálogo (spec 2026-10-09 §4)."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Modo = Literal["presentar", "practicar", "comprobar"]


class EvidenciaIn(BaseModel):
    # Lo genera el teléfono: reenviar la misma evidencia no la cuenta dos veces.
    id: UUID
    run_id: UUID
    dinamica: str
    modo: Modo
    item: str
    faceta: str
    acierto: bool
    pistas: int = Field(ge=0, le=50)
    ms: int = Field(ge=0, le=3_600_000)
    detalle: dict | None = None
