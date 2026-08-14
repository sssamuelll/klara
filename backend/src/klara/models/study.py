"""El taller (F0): tarjetas de tema libre, aisladas del dominio de alemán.

Tablas nuevas a propósito. `vocab_items` modela una palabra alemana (lema,
género, IPA, CEFR); una tarjeta del taller es dos caras de texto y unas
etiquetas. Colgarlas de `user_cards` habría exigido una fila fantasma de vocab
por tarjeta. Los dos sistemas conviven declaradamente (deuda con dueña: Lyra).

Lo que sí comparten es el scheduler: `StudyCard` cumple el Protocol `FsrsCard`
de `services/srs_engine.py` con los mismos nueve atributos que `UserCard`, y
`test_srs_engine_paridad.py` se pone rojo si alguna de las dos deriva.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from klara.models.base import Base, created_ts, nullable_ts, pg_enum, updated_ts, uuid_pk
from klara.models.enums import CardState, ReviewRating


class StudyCard(Base):
    __tablename__ = "study_cards"
    __table_args__ = (
        Index("ix_study_card_due", "user_id", "next_review_at"),
        Index("ix_study_card_batch", "user_id", "batch_id"),
    )

    id: Mapped[uuid_pk]
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Sin TAB/CR/LF (validado en frontera): es lo que hace que el TSV de
    # /taller/export no necesite escapado ni quoting.
    front: Mapped[str] = mapped_column(Text, nullable=False)
    back: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list, server_default="{}"
    )
    # Lote de autoría, generado por el cliente: hace idempotente el guardado
    # (doble clic, reintento, respuesta perdida) y es la unidad que mide la
    # regla de decisión — cuántas sesiones de autoría hubo, no solo cuántas
    # tarjetas.
    batch_id: Mapped[UUID] = mapped_column(nullable=False)
    # Borrado blando: el ledger de repasos sobrevive al archivado.
    archived_at: Mapped[nullable_ts]

    # --- estado FSRS: los nueve del Protocol FsrsCard ---
    state: Mapped[CardState] = mapped_column(
        pg_enum(CardState, name="card_state"),
        default=CardState.NEW,
        nullable=False,
    )
    stability: Mapped[float | None] = mapped_column(Float, nullable=True)
    difficulty: Mapped[float | None] = mapped_column(Float, nullable=True)
    fsrs_step: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fsrs_last_review: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    interval_days: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # NOT NULL, a diferencia de user_cards: una tarjeta nace vencida con
    # next_review_at = created_at. La cola sale ordenada (la más vieja primero)
    # sin la rama `is_(None)` que arrastra la consulta del alemán.
    next_review_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    repetitions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # `ease` no se copia: columna legacy congelada en user_cards, el motor FSRS
    # no la toca.

    created_at: Mapped[created_ts]
    updated_at: Mapped[updated_ts]


class StudyCardReview(Base):
    __tablename__ = "study_card_reviews"
    __table_args__ = (
        CheckConstraint("device IN ('desktop', 'mobile')", name="ck_study_review_device"),
        Index("ix_study_review_user_time", "user_id", "reviewed_at"),
    )

    id: Mapped[uuid_pk]
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    study_card_id: Mapped[UUID] = mapped_column(
        ForeignKey("study_cards.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[ReviewRating] = mapped_column(
        pg_enum(ReviewRating, name="review_rating"),
        nullable=False,
    )
    elapsed_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prev_interval_days: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    new_interval_days: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # Obligatorio en el request; el servidor no lo adivina del User-Agent y no
    # tiene default. Con NOT NULL + CHECK es un invariante de esquema, no un
    # criterio de éxito.
    device: Mapped[str] = mapped_column(String(16), nullable=False)
    reviewed_at: Mapped[created_ts]
