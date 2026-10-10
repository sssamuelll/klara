"""Klara en tres idiomas (spec 2026-10-09 §2.2): el estado FSRS de cada faceta,
el registro de evidencias y las corridas del reproductor.

`UserFacet` cumple el Protocol `FsrsCard` de `services/srs_engine.py` con los
mismos nueve atributos que `UserCard` y `StudyCard`; `test_srs_engine_paridad.py`
se pone rojo si alguna de las tres deriva.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from klara.models.base import Base, created_ts, nullable_ts, pg_enum, updated_ts, uuid_pk
from klara.models.enums import CardState, ReviewRating


class LessonRun(Base):
    """Una corrida del reproductor: la línea de Hoy, «otra lección» o una lección
    repetida desde el mapa. La posición en el mapa sale de aquí (spec §2.2)."""

    __tablename__ = "lesson_runs"
    __table_args__ = (
        CheckConstraint("origen IN ('hoy', 'mapa')", name="ck_lesson_run_origen"),
        Index("ix_lesson_run_user", "user_id", "idioma", "finished_at"),
    )

    id: Mapped[uuid_pk]
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    idioma: Mapped[str] = mapped_column(String(5), nullable=False)
    # Null en una corrida que fue solo de repasos.
    leccion_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    origen: Mapped[str] = mapped_column(String(8), nullable=False)
    # Cuántas actividades de repaso traía la sesión: Hoy lo enseña en la línea hecha.
    repasos: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    started_at: Mapped[created_ts]
    finished_at: Mapped[nullable_ts]


class UserFacet(Base):
    """El estado FSRS de una (usuario, ítem, faceta). Nace con la primera
    evidencia en `comprobar` de esa faceta (spec §2.2)."""

    __tablename__ = "user_facets"
    __table_args__ = (
        UniqueConstraint("user_id", "item_key", "faceta", name="uq_user_facet"),
        Index("ix_user_facet_due", "user_id", "idioma", "next_review_at"),
    )

    id: Mapped[uuid_pk]
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # El prefijo de la clave, copiado para consultar por idioma sin LIKE.
    idioma: Mapped[str] = mapped_column(String(5), nullable=False)
    item_key: Mapped[str] = mapped_column(Text, nullable=False)
    faceta: Mapped[str] = mapped_column(String(20), nullable=False)

    # --- estado FSRS: los nueve del Protocol FsrsCard ---
    state: Mapped[CardState] = mapped_column(
        pg_enum(CardState, name="card_state"), default=CardState.NEW, nullable=False
    )
    stability: Mapped[float | None] = mapped_column(Float, nullable=True)
    difficulty: Mapped[float | None] = mapped_column(Float, nullable=True)
    fsrs_step: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fsrs_last_review: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    interval_days: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    next_review_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    repetitions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[created_ts]
    updated_at: Mapped[updated_ts]


class FacetReview(Base):
    """Una evidencia, de cualquier modo. Sin FK a `user_facets`: la de práctica
    llega antes de que exista la fila."""

    __tablename__ = "facet_reviews"
    __table_args__ = (
        CheckConstraint(
            "modo IN ('presentar', 'practicar', 'comprobar')", name="ck_facet_review_modo"
        ),
        Index("ix_facet_review_user_time", "user_id", "created_at"),
    )

    # Lo genera el teléfono: reenviar la misma evidencia no la cuenta dos veces.
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("lesson_runs.id", ondelete="CASCADE"), nullable=False
    )
    idioma: Mapped[str] = mapped_column(String(5), nullable=False)
    item_key: Mapped[str] = mapped_column(Text, nullable=False)
    faceta: Mapped[str] = mapped_column(String(20), nullable=False)
    dinamica: Mapped[str] = mapped_column(String(30), nullable=False)
    modo: Mapped[str] = mapped_column(String(12), nullable=False)
    acierto: Mapped[bool] = mapped_column(Boolean, nullable=False)
    pistas: Mapped[int] = mapped_column(Integer, nullable=False)
    ms: Mapped[int] = mapped_column(Integer, nullable=False)
    # Solo en `comprobar`: la nota que movió FSRS.
    nota: Mapped[ReviewRating | None] = mapped_column(
        pg_enum(ReviewRating, name="review_rating"), nullable=True
    )
    # El resumen propio de la dinámica, nunca los datos crudos. Sin detalle, NULL de
    # SQL y no el `null` de JSON (solo cambia cómo se escribe, no la columna).
    detalle: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    created_at: Mapped[created_ts]
