"""La respuesta de GET /today (spec 2026-10-09 §5.1): una línea por idioma."""

from typing import Literal

from pydantic import BaseModel

from klara.schemas.catalogo import LeccionRef


class HechoHoy(BaseModel):
    repasos: int
    leccion: str | None


class Linea(BaseModel):
    idioma: str
    estado: Literal["hecha", "ahora", "pendiente"]
    minutos: int
    repasos: int
    leccion: LeccionRef | None
    hecho: HechoHoy | None


class TodayOut(BaseModel):
    lineas: list[Linea]
