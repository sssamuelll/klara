"""Lo que entra y sale de las rutas del catálogo (spec 2026-10-09 §4)."""

import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from klara.catalogo.dinamicas import CAP_REPASOS

Modo = Literal["presentar", "practicar", "comprobar"]

# Una actividad abierta más de una hora (el teléfono en segundo plano) cuenta como
# una hora: rechazarla perdía la respuesta, y la nota sale `hard` igual.
MS_MAX = 3_600_000
# El detalle es un resumen: el de un trazo con todos sus rechazos no llega a 1 KB.
DETALLE_MAX_BYTES = 16 * 1024


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
    ms: int = Field(ge=0)
    detalle: dict | None = None

    @field_validator("ms")
    @classmethod
    def _recortar_ms(cls, ms: int) -> int:
        return min(ms, MS_MAX)

    @field_validator("detalle")
    @classmethod
    def _detalle_con_tope(cls, detalle: dict | None) -> dict | None:
        tam = len(json.dumps(detalle, ensure_ascii=False).encode()) if detalle else 0
        if tam > DETALLE_MAX_BYTES:
            raise ValueError(f"detalle de más de {DETALLE_MAX_BYTES} bytes")
        return detalle


class ActividadOut(BaseModel):
    id: str
    dinamica: str
    modo: Modo
    items: list[str]
    faceta: str
    repaso: bool
    contenido: dict


class LeccionRef(BaseModel):
    id: str
    titulo: str
    bajada: str


class SesionOut(BaseModel):
    idioma: str
    leccion: LeccionRef | None
    actividades: list[ActividadOut]


class RunIn(BaseModel):
    idioma: str
    leccion_id: str | None = None
    origen: Literal["hoy", "mapa"]
    repasos: int = Field(default=0, ge=0, le=CAP_REPASOS)


class RunOut(BaseModel):
    id: UUID


class FinOut(BaseModel):
    # Las facetas de ese idioma que vencen en las próximas 24 horas.
    manana: int


class EvidenciasIn(BaseModel):
    evidencias: list[EvidenciaIn] = Field(min_length=1, max_length=50)


class EvidenciasOut(BaseModel):
    guardadas: int


class MapaResumen(BaseModel):
    idioma: str
    estudias: bool
    nivel: str
    progreso: float
    vencen: int
