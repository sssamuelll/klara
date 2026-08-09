"""Perfil de Aprendizaje — capa declarada (F1.5).

Una fila por usuario, pisada en cada guardado. Es el cuestionario que define
cómo aprende cada quien; las herramientas de un curso son f(tipo, perfil) (D-K).

`facts` y `synthesis` son DERIVADOS de `answers` y salen de la misma llamada,
así que comparten una sola marca de frescura: `derived_for_version`. Cuando es
menor que `version`, hay respuestas más nuevas que la síntesis mostrada y la UI
lo dice — nunca se presenta una síntesis vieja como fresca.

`timings` es lo único irreparable de esta tabla: un costo-por-pregunta mal
medido hoy no se arregla después, y la poda por valor informativo (#138 v2a)
se entrena con eso. Su semántica de medición vive en la spec, no acá.
"""

from uuid import UUID

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from klara.models.base import Base, updated_ts


class LearnerProfile(Base):
    __tablename__ = "learner_profile"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    #: {question_id: valor | [valores] | {opcion: "sirve"|"no"} | null}.
    #: null = el usuario la vio y la saltó; clave ausente = no llegó al cliente.
    answers: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    #: {question_id: elapsed_ms} — costo real de responder, sin tiempo oculto.
    timings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    #: átomos de la allow-list cerrada; NULL = pendiente o falló la generación.
    facts: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    #: prosa con procedencia; NULL = pendiente o falló la generación.
    synthesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: versión de `answers` que produjo facts+synthesis. < version ⇒ stale.
    derived_for_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[updated_ts]
