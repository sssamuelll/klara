"""Carga y valida el catálogo (spec §2.1). Si algo no cuadra, el servidor no
arranca: `CatalogoInvalido` junta TODOS los errores, no solo el primero."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

from klara.catalogo.dinamicas import DINAMICAS, ejercita
from klara.catalogo.facetas import faceta_valida, partes, tipo_de
from klara.catalogo.modelo import (
    Actividad,
    Catalogo,
    InventarioKana,
    Item,
    Leccion,
    LeccionCompleta,
    Mapa,
)
from klara.catalogo.plantillas import PLANTILLAS

RAIZ_MAPAS = Path(__file__).resolve().parent.parent / "mapas"


class CatalogoInvalido(Exception):
    def __init__(self, errores: list[str]):
        self.errores = errores
        super().__init__("catálogo inválido:\n- " + "\n- ".join(errores))


def _leer[M: BaseModel](path: Path, modelo: type[M], errores: list[str]) -> M | None:
    try:
        return modelo.model_validate(json.loads(path.read_text(encoding="utf-8")))
    # ValueError: JSONDecodeError, UnicodeDecodeError y el ValidationError de pydantic.
    except (OSError, ValueError) as e:
        errores.append(f"{path.parent.name}/{path.name}: {e}")
        return None


def _inventario_ja(dir_: Path, errores: list[str]) -> dict[str, Item]:
    inv = _leer(dir_ / "kana.json", InventarioKana, errores)
    if inv is None:
        return {}
    items: dict[str, Item] = {}
    for k in inv.kana:
        clave = f"ja:kana:{k.kana}"
        if clave in items:
            errores.append(f"ja/kana.json: {k.kana} repetido")
        if not k.trazos:
            errores.append(f"ja/kana.json: {k.kana} sin trazos")
        if not (dir_ / "audio" / k.audio).is_file():
            errores.append(f"ja/kana.json: falta el audio {k.audio}")
        items[clave] = k
    for k in inv.kana:
        for c in k.confusiones:
            if f"ja:kana:{c}" not in items:
                errores.append(
                    f"ja/kana.json: {k.kana} confunde con {c}, que no está en el inventario"
                )
    return items


# Un cargador de inventario por idioma. Los planes 2 y 3 agregan «de» y «en».
INVENTARIOS: dict[str, Callable[[Path, list[str]], dict[str, Item]]] = {"ja": _inventario_ja}


def _validar_actividad(
    a: Actividad, donde: str, items: dict[str, Item], errores: list[str]
) -> None:
    d = DINAMICAS.get(a.dinamica)
    if d is None:
        errores.append(f"{donde}: dinámica desconocida {a.dinamica!r}")
        return
    if a.modo not in d.modos:
        errores.append(f"{donde}: {a.dinamica} no soporta el modo {a.modo}")
    for item in a.items:
        if item not in items:
            errores.append(f"{donde}: el ítem {item!r} no existe")
        elif not faceta_valida(item, a.faceta):
            errores.append(f"{donde}: {a.faceta!r} no es faceta de {tipo_de(item)}")
        elif not ejercita(d, tipo_de(item), a.faceta):
            errores.append(f"{donde}: {a.dinamica} no ejercita {tipo_de(item)} × {a.faceta}")


def _expandir(leccion: Leccion, donde: str, errores: list[str]) -> Leccion:
    if leccion.plantilla is None:
        if not leccion.actividades:
            errores.append(f"{donde}: sin plantilla ni actividades")
        return leccion
    plantilla = PLANTILLAS.get(leccion.plantilla)
    if plantilla is None:
        errores.append(f"{donde}: plantilla desconocida {leccion.plantilla!r}")
        return leccion
    if not leccion.items:
        errores.append(f"{donde}: la plantilla {leccion.plantilla} necesita items")
        return leccion
    return leccion.model_copy(
        update={"actividades": plantilla(leccion.items) + leccion.actividades}
    )


def _comprueba_lo_que_practica(leccion: Leccion, donde: str, errores: list[str]) -> None:
    def pares(modo: str) -> set[tuple[str, str]]:
        return {(i, a.faceta) for a in leccion.actividades if a.modo == modo for i in a.items}

    for item, faceta in sorted(pares("practicar") - pares("comprobar")):
        errores.append(f"{donde}: practica {item} × {faceta} y no lo comprueba")


def cargar_catalogo(raiz: Path = RAIZ_MAPAS) -> Catalogo:
    errores: list[str] = []
    mapas: dict[str, Mapa] = {}
    items: dict[str, Item] = {}
    lecciones: dict[str, LeccionCompleta] = {}

    for dir_ in sorted(
        p for p in raiz.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))
    ):
        idioma = dir_.name
        cargar_inventario = INVENTARIOS.get(idioma)
        if cargar_inventario is None:
            errores.append(f"{idioma}: no hay inventario registrado para este idioma")
            continue
        items.update(cargar_inventario(dir_, errores))
        mapa = _leer(dir_ / "mapa.json", Mapa, errores)
        if mapa is None:
            continue
        if mapa.idioma != idioma:
            errores.append(f"{idioma}/mapa.json: dice idioma {mapa.idioma!r}")
        unidades_vistas: set[str] = set()
        for unidad in mapa.unidades:
            if unidad.id in unidades_vistas:
                errores.append(f"{idioma}/{unidad.id}: unidad repetida")
            unidades_vistas.add(unidad.id)
            if unidad.nivel not in mapa.escala:
                errores.append(
                    f"{idioma}/{unidad.id}: el nivel {unidad.nivel!r} no está en la escala"
                )
            ids: set[str] = set()
            de_la_unidad: set[str] = set()
            for leccion in unidad.lecciones:
                donde = f"{idioma}/{unidad.id}/{leccion.id}"
                if leccion.id in ids:
                    errores.append(f"{donde}: id de lección repetido")
                ids.add(leccion.id)
                expandida = _expandir(leccion, donde, errores)
                for n, a in enumerate(expandida.actividades):
                    _validar_actividad(a, f"{donde}#{n}", items, errores)
                    for item in a.items:
                        if item in items and partes(item)[0] != idioma:
                            errores.append(f"{donde}#{n}: {item} es de otro idioma")
                _comprueba_lo_que_practica(expandida, donde, errores)
                de_la_unidad.update(i for a in expandida.actividades for i in a.items)
                lecciones[donde] = LeccionCompleta(
                    id=donde, idioma=idioma, unidad=unidad.id, leccion=expandida
                )
            for fila in unidad.sabes.filas or ():
                for item in fila:
                    if item is not None and item not in de_la_unidad:
                        errores.append(
                            f"{idioma}/{unidad.id}: «lo que sabes» nombra {item}, que no está en la unidad"
                        )
        mapas[idioma] = mapa

    if errores:
        raise CatalogoInvalido(errores)
    return Catalogo(raiz=raiz, mapas=mapas, items=items, lecciones=lecciones)


@lru_cache(maxsize=1)
def get_catalogo() -> Catalogo:
    """El catálogo de la app. `KLARA_MAPAS_DIR` lo apunta a otra carpeta (los tests)."""
    raiz = os.environ.get("KLARA_MAPAS_DIR")
    return cargar_catalogo(Path(raiz) if raiz else RAIZ_MAPAS)
