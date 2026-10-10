"""El catálogo como datos (spec §2.1): mapas, unidades, lecciones, actividades e
inventarios. Aquí solo hay forma; la validación cruzada vive en `cargar.py`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Modo = Literal["presentar", "practicar", "comprobar"]


class _Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Actividad(_Estricto):
    dinamica: str
    modo: Modo
    items: tuple[str, ...] = Field(min_length=1)
    faceta: str


class Leccion(_Estricto):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    titulo: str
    bajada: str
    plantilla: str | None = None
    items: tuple[str, ...] = ()
    actividades: tuple[Actividad, ...] = ()


class Sabes(_Estricto):
    vista: Literal["tabla", "lista"]
    filas: tuple[tuple[str | None, ...], ...] | None = None


class Unidad(_Estricto):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    titulo: str
    nivel: str
    puedo: tuple[str, ...] = Field(min_length=1)
    sabes: Sabes
    lecciones: tuple[Leccion, ...] = Field(min_length=1)


class Mapa(_Estricto):
    idioma: str
    escala: tuple[str, ...] = Field(min_length=1)
    unidades: tuple[Unidad, ...] = Field(min_length=1)


class Kana(_Estricto):
    kana: str = Field(min_length=1, max_length=1)
    romaji: str
    # Lo que suena. お y を suenan igual: `oír` nunca los pone juntos.
    sonido: str
    confusiones: tuple[str, ...] = ()
    trazos: tuple[str, ...] = ()
    audio: str = Field(pattern=r"^[a-z0-9_-]+\.mp3$")
    mnemotecnia: str


class InventarioKana(_Estricto):
    fuente: str
    kana: tuple[Kana, ...]


# Los planes 2 y 3 amplían la unión (Sustantivo, Caso, Contraste).
Item = Kana


@dataclass(frozen=True)
class LeccionCompleta:
    id: str  # "ja/hiragana/ka"
    idioma: str
    unidad: str
    leccion: Leccion  # con `actividades` ya expandidas


@dataclass(frozen=True)
class Catalogo:
    raiz: Path
    mapas: dict[str, Mapa]
    items: dict[str, Item]
    # En el orden de los mapas: la siguiente lección es la primera sin terminar.
    lecciones: dict[str, LeccionCompleta]

    def lecciones_de(self, idioma: str) -> list[LeccionCompleta]:
        return [lec for lec in self.lecciones.values() if lec.idioma == idioma]

    def audio_path(self, idioma: str, archivo: str) -> Path:
        return self.raiz / idioma / "audio" / archivo
