"""Componer la sesión de una línea (spec 2026-10-09 §4): hasta CAP_REPASOS
facetas vencidas y la siguiente lección del mapa. Hoy usa la misma composición
para estimar los minutos, así los que promete son los de la sesión."""

from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from klara.catalogo.dinamicas import CAP_REPASOS, DINAMICA_DE_REPASO, DINAMICAS
from klara.catalogo.facetas import tipo_de
from klara.catalogo.generar import Contexto, generar
from klara.catalogo.modelo import Actividad, Catalogo, LeccionCompleta
from klara.models import LessonRun, User, UserFacet

# El orden en que se listan los mapas (Ajustes y, en el plan 4, Biblioteca).
IDIOMAS_ORDEN = ("de", "ja", "en")


@dataclass(frozen=True)
class Plan:
    idioma: str
    repasos: tuple[Actividad, ...]
    leccion: LeccionCompleta | None
    # Ítems ya presentados: los de las lecciones hechas y los que tienen fila.
    # Los distractores de los repasos salen solo de aquí.
    vistos: frozenset[str] = frozenset()

    @property
    def actividades(self) -> tuple[Actividad, ...]:
        return self.repasos + (self.leccion.leccion.actividades if self.leccion else ())


def idiomas_de_estudio(user: User, cat: Catalogo) -> list[str]:
    """Los idiomas de las líneas de Hoy: `study_languages`, o el idioma de estudio
    si no se eligió nada. Solo los que tienen mapa (spec §2.2)."""
    base = user.study_languages or [user.target_language]
    return [i for i in base if i in cat.mapas]


def orden_de_mapas(cat: Catalogo) -> list[str]:
    def clave(i: str) -> tuple[int, str]:
        return (IDIOMAS_ORDEN.index(i) if i in IDIOMAS_ORDEN else len(IDIOMAS_ORDEN), i)

    return sorted(cat.mapas, key=clave)


def huerfanas(claves: set[str], cat: Catalogo) -> list[str]:
    """Las claves de `user_facets` que ya no están en el catálogo (spec §2.1)."""
    return sorted(claves - set(cat.items))


def _ordenable(restan: Counter[str], tomado: str) -> bool:
    """Si ahora sale una faceta de `tomado`, ¿lo que queda se puede ordenar sin juntar
    dos del mismo ítem? De las n que quedan, ningún ítem puede tener más de ceil(n/2),
    y `tomado`, que no puede abrir, no más de floor(n/2)."""
    n = restan.total() - 1  # las que quedan después de sacar esa
    return all(
        (c - 1 <= n // 2) if item == tomado else (c <= (n + 1) // 2) for item, c in restan.items()
    )


def separar_mismo_item(pares: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Reordena para que no vayan dos facetas del mismo ítem seguidas, respetando el
    orden de vencimiento todo lo posible: sale la primera pendiente que no repite el
    ítem anterior y deja un resto aún ordenable. Si ninguna lo deja (un ítem trae
    demasiadas para separarlas), sale la primera que no repite, o la primera sin más."""
    pendientes = list(pares)
    restan = Counter(item for item, _ in pendientes)
    out: list[tuple[str, str]] = []
    while pendientes:
        ultimo = out[-1][0] if out else None
        otros = [k for k, (item, _) in enumerate(pendientes) if item != ultimo]
        k = next(
            (k for k in otros if _ordenable(restan, pendientes[k][0])),
            otros[0] if otros else 0,
        )
        restan[pendientes[k][0]] -= 1
        out.append(pendientes.pop(k))
    return out


async def lecciones_hechas(db: AsyncSession, user_id: UUID, idioma: str) -> frozenset[str]:
    """Una lección está hecha si tiene una corrida de Hoy terminada (spec §2.2)."""
    filas = await db.execute(
        select(LessonRun.leccion_id).where(
            LessonRun.user_id == user_id,
            LessonRun.idioma == idioma,
            LessonRun.origen == "hoy",
            LessonRun.finished_at.is_not(None),
            LessonRun.leccion_id.is_not(None),
        )
    )
    return frozenset(filas.scalars())


def siguiente_leccion(cat: Catalogo, idioma: str, hechas: frozenset[str]) -> LeccionCompleta | None:
    return next((lec for lec in cat.lecciones_de(idioma) if lec.id not in hechas), None)


async def items_vistos(
    db: AsyncSession, cat: Catalogo, user_id: UUID, idioma: str, hechas: frozenset[str]
) -> frozenset[str]:
    con_fila = await db.execute(
        select(UserFacet.item_key)
        .where(UserFacet.user_id == user_id, UserFacet.idioma == idioma)
        .distinct()
    )
    de_lecciones = {
        i
        for lec in cat.lecciones_de(idioma)
        if lec.id in hechas
        for a in lec.leccion.actividades
        for i in a.items
    }
    return frozenset(de_lecciones | {i for i in con_fila.scalars() if i in cat.items})


async def contar_vencidas(
    db: AsyncSession, cat: Catalogo, user_id: UUID, idioma: str, hasta: datetime
) -> int:
    """Las que la sesión repasaría, sin tope: «mañana» y `vencen` no prometen huérfanas."""
    return len(await _vencidas(db, cat, user_id, idioma, hasta))


async def _vencidas(
    db: AsyncSession, cat: Catalogo, user_id: UUID, idioma: str, hasta: datetime
) -> list[tuple[str, str]]:
    filas = await db.execute(
        select(UserFacet.item_key, UserFacet.faceta)
        .where(
            UserFacet.user_id == user_id,
            UserFacet.idioma == idioma,
            UserFacet.next_review_at <= hasta,
        )
        .order_by(UserFacet.next_review_at, UserFacet.item_key, UserFacet.faceta)
    )
    # Las huérfanas (ítem fuera del catálogo) y las facetas sin dinámica de repaso se ignoran (spec §2.1).
    return [
        (i, f) for i, f in filas.all() if i in cat.items and (tipo_de(i), f) in DINAMICA_DE_REPASO
    ]


async def componer(
    db: AsyncSession,
    cat: Catalogo,
    user_id: UUID,
    idioma: str,
    ahora: datetime,
    *,
    con_repasos: bool = True,
) -> Plan:
    pares = (await _vencidas(db, cat, user_id, idioma, ahora))[:CAP_REPASOS] if con_repasos else []
    repasos = tuple(
        Actividad(
            dinamica=DINAMICA_DE_REPASO[(tipo_de(i), f)], modo="comprobar", items=(i,), faceta=f
        )
        for i, f in separar_mismo_item(pares)
    )
    hechas = await lecciones_hechas(db, user_id, idioma)
    return Plan(
        idioma=idioma,
        repasos=repasos,
        leccion=siguiente_leccion(cat, idioma, hechas),
        vistos=await items_vistos(db, cat, user_id, idioma, hechas),
    )


def plan_para_repetir(leccion: LeccionCompleta, vistos: frozenset[str]) -> Plan:
    """Una lección hecha, repetida desde el mapa: todo en práctica, nada mueve FSRS."""
    practicas = tuple(
        a.model_copy(update={"modo": "practicar"}) if a.modo == "comprobar" else a
        for a in leccion.leccion.actividades
    )
    copia = LeccionCompleta(
        id=leccion.id,
        idioma=leccion.idioma,
        unidad=leccion.unidad,
        leccion=leccion.leccion.model_copy(update={"actividades": practicas}),
    )
    return Plan(idioma=leccion.idioma, repasos=(), leccion=copia, vistos=vistos)


def minutos(plan: Plan) -> int:
    segundos = sum(DINAMICAS[a.dinamica].segundos[a.modo] for a in plan.actividades)
    return math.ceil(segundos / 60)


def contenido(cat: Catalogo, plan: Plan, semilla: int) -> list[dict]:
    rng = random.Random(semilla)
    de_la_leccion = frozenset(
        i for a in (plan.leccion.leccion.actividades if plan.leccion else ()) for i in a.items
    )
    ctx_repaso = Contexto(rng=rng, conocidos=plan.vistos)
    ctx_leccion = Contexto(rng=rng, conocidos=plan.vistos | de_la_leccion)
    n_repasos = len(plan.repasos)
    return [
        {
            "id": f"a{n}",
            "dinamica": a.dinamica,
            "modo": a.modo,
            "items": list(a.items),
            "faceta": a.faceta,
            "repaso": n < n_repasos,
            "contenido": generar(cat, a, ctx_repaso if n < n_repasos else ctx_leccion),
        }
        for n, a in enumerate(plan.actividades)
    ]
