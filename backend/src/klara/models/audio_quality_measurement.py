"""Una fila por toma de micrófono: los números sobre los que el gate decidió.

Por qué una tabla y no el log (issue #120, punto 4): esto es una MUESTRA de
medición, no una traza de operación. Los umbrales de `audio_quality` vienen
heredados de speechtotext y nunca se calibraron contra grabaciones reales de
aprendices; calibrarlos exige la distribución completa — las tomas aceptadas
tanto como la cola de rechazos — acumulada durante semanas y consultable.
El log de un contenedor no es ninguna de las dos cosas: vive en el json-file
del contenedor, que `docker compose up -d` borra en cada despliegue.

Se guardan números, nunca audio ni texto: nada aquí identifica QUÉ dijo el
usuario, sólo cómo sonaba la señal.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from klara.models.base import Base, created_ts, uuid_pk


class AudioQualityMeasurement(Base):
    __tablename__ = "audio_quality_measurements"
    # Las dos preguntas de calibración son "¿cómo se distribuye X en lo
    # aceptado?" y "¿qué se rechazó y por qué, en el tiempo?". Un índice
    # (verdict, measured_at) sirve a ambas.
    __table_args__ = (Index("ix_audio_quality_verdict_time", "verdict", "measured_at"),)

    id: Mapped[uuid_pk]
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # "score" | "speak" | "quiz_mc" — cuál de los tres endpoints con gate la
    # produjo. Importa para calibrar: una toma de /speak es conversación libre
    # y una de /score es una frase leída, y no suenan igual.
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    # "ok" | "rejected"
    verdict: Mapped[str] = mapped_column(String(16), nullable=False)
    # Códigos de rechazo (silence, too_short, level_too_low, clipping). Lista
    # vacía cuando pasó. JSONB porque las razones crecen sin migración.
    reasons: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # La medición: los mismos campos que _medicion() emite al log.
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    voice_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    speech_rms_dbfs: Mapped[float] = mapped_column(Float, nullable=False)
    clip_rms_dbfs: Mapped[float] = mapped_column(Float, nullable=False)
    peak_dbfs: Mapped[float] = mapped_column(Float, nullable=False)
    noise_floor_dbfs: Mapped[float | None] = mapped_column(Float, nullable=True)
    snr_db: Mapped[float | None] = mapped_column(Float, nullable=True)
    clipping_ratio: Mapped[float] = mapped_column(Float, nullable=False)

    # Estado de la ganancia. input_speech_rms_dbfs es el nivel ANTES del boost
    # y sólo existe cuando hubo boost — sin él no se puede saber qué tan lejos
    # del objetivo llegan los micrófonos reales, que es medio issue #120.
    applied_gain_db: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    gain_limited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    input_speech_rms_dbfs: Mapped[float | None] = mapped_column(Float, nullable=True)

    measured_at: Mapped[created_ts]
