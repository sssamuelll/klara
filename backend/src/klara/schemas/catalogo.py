"""Lo que entra y sale de las rutas del catálogo (spec 2026-10-09 §4)."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from klara.catalogo.dinamicas import CAP_REPASOS

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
