"""Entrada única de audio para los endpoints con gate: transcodifica, evalúa y
guarda la medición.

Existe para que la muestra de calidad de audio se escriba UNA vez y en UN
lugar. Las dos salidas del gate (aceptada y rechazada) son igual de
necesarias para calibrar un umbral, y la rechazada sale por excepción; sin
este envoltorio, cada uno de los tres routers tendría que repetir el mismo
try/except y ninguno tendría por qué acordarse. Ver issue #120, punto 4.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import structlog
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from klara.models import AudioQualityMeasurement
from klara.pronunciation.audio_quality import AudioQualityRejected, transcode_and_gate

log = structlog.get_logger(__name__)

# Los tres endpoints con gate. No es un enum porque nada ramifica sobre el
# valor: es una etiqueta de muestreo que se lee en SQL.
Source = str


async def _record(
    db: AsyncSession,
    user_id: UUID,
    source: Source,
    measurement: dict[str, object],
) -> None:
    """Persiste la medición sin poder tumbar la petición.

    Falla abierto, igual que el gate: que la analítica reviente no puede
    convertir una toma que funcionaba en un 500. Se hace commit explícito
    porque la sesión por petición se cierra sin commitear (ver
    dependencies.db_session), y en la ruta de rechazo no hay después.
    """
    if not measurement:  # WAV ilegible: no hubo números que medir.
        return
    try:
        db.add(AudioQualityMeasurement(user_id=user_id, source=source, **measurement))
        await db.commit()
    except Exception as e:  # analítica: se traga todo, nunca tumba la petición
        await db.rollback()
        log.warning("pronunciation.audio_quality_not_recorded", error=str(e), source=source)


async def gate_upload(
    audio_bytes: bytes,
    *,
    locale: str,
    db: AsyncSession,
    user_id: UUID,
    source: Source,
) -> Path:
    """Devuelve el WAV listo para Azure, dejando la medición en la tabla.

    Propaga TranscodeError / FfmpegMissingError tal cual (el router los
    traduce a su propio código HTTP) y AudioQualityRejected como 422, igual
    que antes — con la fila ya escrita.
    """
    try:
        result = await run_in_threadpool(transcode_and_gate, audio_bytes, locale=locale)
    except AudioQualityRejected as rejected:
        await _record(db, user_id, source, rejected.measurement)
        raise
    await _record(db, user_id, source, result.measurement)
    return result.wav_path
