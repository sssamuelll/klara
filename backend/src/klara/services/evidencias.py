"""Registrar evidencias (spec 2026-10-09 §4): validar contra el catálogo, guardar
en el registro sin duplicar, y mover FSRS solo en `comprobar`."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from klara.catalogo.dinamicas import DINAMICAS, ejercita
from klara.catalogo.facetas import faceta_valida, idioma_de, tipo_de
from klara.catalogo.modelo import Catalogo
from klara.catalogo.nota import nota as calcular_nota
from klara.models import FacetReview, LessonRun, UserFacet
from klara.models.enums import CardState, ReviewRating
from klara.schemas.catalogo import EvidenciaIn
from klara.services.srs_engine import apply_review


class EvidenciaInvalida(ValueError):
    """Una evidencia que no cuadra con el catálogo o con la cuenta: 422."""


def validar(cat: Catalogo, ev: EvidenciaIn) -> None:
    d = DINAMICAS.get(ev.dinamica)
    if d is None:
        raise EvidenciaInvalida(f"dinámica desconocida: {ev.dinamica}")
    if ev.modo not in d.modos:
        raise EvidenciaInvalida(f"{ev.dinamica} no soporta el modo {ev.modo}")
    if ev.item not in cat.items:
        raise EvidenciaInvalida(f"ítem desconocido: {ev.item}")
    if not faceta_valida(ev.item, ev.faceta) or not ejercita(d, tipo_de(ev.item), ev.faceta):
        raise EvidenciaInvalida(f"{ev.dinamica} no ejercita {ev.item} con {ev.faceta}")


async def _aplicar(
    db: AsyncSession, user_id: UUID, ev: EvidenciaIn, n: ReviewRating, ahora: datetime
) -> None:
    # La fila nace con la primera prueba de esa faceta (spec §2.2). Los campos van
    # explícitos: el motor lee `state` y `repetitions` antes de cualquier flush.
    await db.execute(
        pg_insert(UserFacet)
        .values(
            user_id=user_id,
            idioma=idioma_de(ev.item),
            item_key=ev.item,
            faceta=ev.faceta,
            state=CardState.NEW,
            interval_days=0.0,
            repetitions=0,
            next_review_at=ahora,
        )
        .on_conflict_do_nothing(constraint="uq_user_facet")
    )
    faceta = (
        await db.execute(
            select(UserFacet)
            .where(
                UserFacet.user_id == user_id,
                UserFacet.item_key == ev.item,
                UserFacet.faceta == ev.faceta,
            )
            .with_for_update()
        )
    ).scalar_one()
    apply_review(faceta, n)


async def registrar(
    db: AsyncSession,
    cat: Catalogo,
    user_id: UUID,
    evidencias: list[EvidenciaIn],
    ahora: datetime,
) -> int:
    """Devuelve cuántas evidencias nuevas se guardaron; las repetidas no cuentan.
    Si una sola no cuadra, no se guarda ninguna."""
    for ev in evidencias:
        validar(cat, ev)
    corridas = {ev.run_id for ev in evidencias}
    propias = set(
        (
            await db.execute(
                select(LessonRun.id).where(
                    LessonRun.id.in_(list(corridas)), LessonRun.user_id == user_id
                )
            )
        ).scalars()
    )
    if propias != corridas:
        raise EvidenciaInvalida("corrida desconocida")

    guardadas = 0
    for ev in evidencias:
        n = (
            calcular_nota(
                acierto=ev.acierto,
                pistas=ev.pistas,
                ms=ev.ms,
                ms_lento=DINAMICAS[ev.dinamica].ms_lento,
            )
            if ev.modo == "comprobar"
            else None
        )
        nueva = (
            await db.execute(
                pg_insert(FacetReview)
                .values(
                    id=ev.id,
                    user_id=user_id,
                    run_id=ev.run_id,
                    idioma=idioma_de(ev.item),
                    item_key=ev.item,
                    faceta=ev.faceta,
                    dinamica=ev.dinamica,
                    modo=ev.modo,
                    acierto=ev.acierto,
                    pistas=ev.pistas,
                    ms=ev.ms,
                    nota=n,
                    detalle=ev.detalle,
                )
                .on_conflict_do_nothing(index_elements=["id"])
                .returning(FacetReview.id)
            )
        ).scalar_one_or_none()
        if nueva is None:
            continue  # ya estaba: reenviarla no la cuenta dos veces
        guardadas += 1
        if n is not None:
            await _aplicar(db, user_id, ev, n, ahora)
    await db.commit()
    return guardadas
