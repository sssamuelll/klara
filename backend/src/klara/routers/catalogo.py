"""El catálogo por HTTP (spec 2026-10-09 §4): componer sesiones, abrir y cerrar
corridas, registrar evidencias, servir el audio del catálogo y resumir los mapas."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select

from klara.catalogo.cargar import get_catalogo
from klara.catalogo.modelo import Catalogo
from klara.dependencies import CurrentUser, DBSession
from klara.models import LessonRun
from klara.schemas.catalogo import (
    ActividadOut,
    EvidenciasIn,
    EvidenciasOut,
    FinOut,
    LeccionRef,
    MapaResumen,
    RunIn,
    RunOut,
    SesionOut,
)
from klara.services.evidencias import EvidenciaInvalida, registrar
from klara.services.sesion import (
    Plan,
    componer,
    contar_vencidas,
    contenido,
    idiomas_de_estudio,
    items_vistos,
    lecciones_hechas,
    orden_de_mapas,
    plan_para_repetir,
    siguiente_leccion,
)

router = APIRouter(tags=["catalogo"])

_ARCHIVO = re.compile(r"[a-z0-9_-]+\.mp3")


def _con_mapa(cat: Catalogo, idioma: str) -> None:
    if idioma not in cat.mapas:
        raise HTTPException(status_code=404, detail="catalogo.idioma_sin_mapa")


def _sesion_out(cat: Catalogo, plan: Plan, ahora: datetime) -> SesionOut:
    lec = plan.leccion
    return SesionOut(
        idioma=plan.idioma,
        leccion=LeccionRef(id=lec.id, titulo=lec.leccion.titulo, bajada=lec.leccion.bajada)
        if lec
        else None,
        actividades=[
            ActividadOut(**a) for a in contenido(cat, plan, semilla=int(ahora.timestamp()))
        ],
    )


@router.get("/sesiones/{idioma}", response_model=SesionOut)
async def get_sesion(
    idioma: str, db: DBSession, user: CurrentUser, repasos: bool = True
) -> SesionOut:
    cat = get_catalogo()
    _con_mapa(cat, idioma)
    ahora = datetime.now(UTC)
    plan = await componer(db, cat, user.id, idioma, ahora, con_repasos=repasos)
    return _sesion_out(cat, plan, ahora)


@router.get("/lecciones/{idioma}/{unidad}/{leccion}", response_model=SesionOut)
async def get_leccion(
    idioma: str, unidad: str, leccion: str, db: DBSession, user: CurrentUser
) -> SesionOut:
    cat = get_catalogo()
    _con_mapa(cat, idioma)
    lec = cat.lecciones.get(f"{idioma}/{unidad}/{leccion}")
    if lec is None:
        raise HTTPException(status_code=404, detail="catalogo.leccion_inexistente")
    hechas = await lecciones_hechas(db, user.id, idioma)
    vistos = await items_vistos(db, cat, user.id, idioma, hechas)
    return _sesion_out(cat, plan_para_repetir(lec, vistos), datetime.now(UTC))


@router.post("/lesson-runs", response_model=RunOut, status_code=201)
async def abrir_corrida(body: RunIn, db: DBSession, user: CurrentUser) -> RunOut:
    cat = get_catalogo()
    _con_mapa(cat, body.idioma)
    if body.leccion_id is not None:
        lec = cat.lecciones.get(body.leccion_id)
        if lec is None or lec.idioma != body.idioma:
            raise HTTPException(status_code=422, detail="catalogo.leccion_inexistente")
    run_id = uuid4()
    db.add(
        LessonRun(
            id=run_id,
            user_id=user.id,
            idioma=body.idioma,
            leccion_id=body.leccion_id,
            origen=body.origen,
            repasos=body.repasos,
        )
    )
    await db.commit()
    return RunOut(id=run_id)


@router.post("/lesson-runs/{run_id}/fin", response_model=FinOut)
async def cerrar_corrida(run_id: UUID, db: DBSession, user: CurrentUser) -> FinOut:
    run = (
        await db.execute(
            select(LessonRun).where(LessonRun.id == run_id, LessonRun.user_id == user.id)
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="catalogo.corrida_inexistente")
    ahora = datetime.now(UTC)
    idioma = run.idioma
    if run.finished_at is None:
        run.finished_at = ahora
        await db.commit()
    return FinOut(manana=await contar_vencidas(db, user.id, idioma, ahora + timedelta(days=1)))


@router.post("/evidencias", response_model=EvidenciasOut)
async def post_evidencias(body: EvidenciasIn, db: DBSession, user: CurrentUser) -> EvidenciasOut:
    try:
        guardadas = await registrar(db, get_catalogo(), user.id, body.evidencias, datetime.now(UTC))
    except EvidenciaInvalida as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return EvidenciasOut(guardadas=guardadas)


@router.get("/audio/{idioma}/{archivo}")
async def get_audio(idioma: str, archivo: str) -> FileResponse:
    """El audio del catálogo es contenido público: sin sesión, para que el
    <audio> del teléfono lo cargue directo."""
    cat = get_catalogo()
    if idioma not in cat.mapas or not _ARCHIVO.fullmatch(archivo):
        raise HTTPException(status_code=404)
    path = cat.audio_path(idioma, archivo)
    if not path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(
        path, media_type="audio/mpeg", headers={"Cache-Control": "public, max-age=86400"}
    )


@router.get("/mapas", response_model=list[MapaResumen])
async def get_mapas(db: DBSession, user: CurrentUser) -> list[MapaResumen]:
    cat = get_catalogo()
    ahora = datetime.now(UTC)
    estudia = set(idiomas_de_estudio(user, cat))
    out: list[MapaResumen] = []
    for idioma in orden_de_mapas(cat):
        mapa = cat.mapas[idioma]
        lecciones = cat.lecciones_de(idioma)
        hechas = await lecciones_hechas(db, user.id, idioma)
        actual = siguiente_leccion(cat, idioma, hechas)
        nivel = (
            next(u.nivel for u in mapa.unidades if u.id == actual.unidad)
            if actual
            else mapa.unidades[-1].nivel
        )
        out.append(
            MapaResumen(
                idioma=idioma,
                estudias=idioma in estudia,
                nivel=nivel,
                progreso=round(sum(1 for lec in lecciones if lec.id in hechas) / len(lecciones), 3),
                vencen=await contar_vencidas(db, user.id, idioma, ahora),
            )
        )
    return out
