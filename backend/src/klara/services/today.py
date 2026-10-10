"""El día de Hoy (spec 2026-10-09 §5.1): una línea por idioma de estudio. Va
primero el que lleva más tiempo sin una línea terminada, contando solo lo
terminado antes de hoy: así el orden no cambia a mitad del día."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from klara.catalogo.cargar import get_catalogo
from klara.models import LessonRun, User
from klara.schemas.catalogo import LeccionRef
from klara.schemas.today import HechoHoy, Linea, TodayOut
from klara.services.sesion import componer, idiomas_de_estudio, minutos

_NUNCA = datetime.min.replace(tzinfo=UTC)


def ordenar_idiomas(idiomas: list[str], ultimas: dict[str, datetime]) -> list[str]:
    """Primero el idioma con la última línea terminada más vieja (o ninguna); con
    empate, el orden de `study_languages`."""
    return sorted(idiomas, key=lambda i: (ultimas.get(i, _NUNCA), idiomas.index(i)))


async def build_today(db: AsyncSession, user: User, *, since: datetime, now: datetime) -> TodayOut:
    cat = get_catalogo()
    idiomas = idiomas_de_estudio(user, cat)
    if not idiomas:
        return TodayOut(lineas=[])

    de_hoy = (
        LessonRun.user_id == user.id,
        LessonRun.origen == "hoy",
        LessonRun.finished_at.is_not(None),
    )
    ultimas = dict(
        (
            await db.execute(
                select(LessonRun.idioma, func.max(LessonRun.finished_at))
                .where(*de_hoy, LessonRun.finished_at < since)
                .group_by(LessonRun.idioma)
            )
        ).all()
    )
    terminadas_hoy = (
        (
            await db.execute(
                select(LessonRun)
                .where(*de_hoy, LessonRun.finished_at >= since)
                .order_by(LessonRun.finished_at)
            )
        )
        .scalars()
        .all()
    )

    lineas: list[Linea] = []
    for idioma in ordenar_idiomas(idiomas, ultimas):
        plan = await componer(db, cat, user.id, idioma, now)
        corridas = [r for r in terminadas_hoy if r.idioma == idioma]
        hecho = None
        if corridas:
            ultima = next(
                (r.leccion_id for r in reversed(corridas) if r.leccion_id in cat.lecciones), None
            )
            hecho = HechoHoy(
                repasos=sum(r.repasos for r in corridas),
                leccion=cat.lecciones[ultima].leccion.titulo if ultima else None,
            )
        if hecho:
            estado = "hecha"
        elif any(linea.estado == "ahora" for linea in lineas):
            estado = "pendiente"
        else:
            estado = "ahora"
        lec = plan.leccion
        lineas.append(
            Linea(
                idioma=idioma,
                estado=estado,
                minutos=minutos(plan),
                repasos=len(plan.repasos),
                leccion=LeccionRef(id=lec.id, titulo=lec.leccion.titulo, bajada=lec.leccion.bajada)
                if lec
                else None,
                hecho=hecho,
            )
        )
    return TodayOut(lineas=lineas)
