from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from klara.models.base import Base, created_ts, pg_enum, updated_ts, uuid_pk
from klara.models.enums import CardState, ReviewRating


class UserCard(Base):
    __tablename__ = "user_cards"
    __table_args__ = (
        UniqueConstraint("user_id", "vocab_item_id", name="uq_user_card_user_vocab"),
        Index("ix_user_card_due", "user_id", "next_review_at"),
    )

    id: Mapped[uuid_pk]
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    vocab_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("vocab_items.id", ondelete="CASCADE"), nullable=False
    )
    ease: Mapped[float] = mapped_column(Float, default=2.5, nullable=False)
    interval_days: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    repetitions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    state: Mapped[CardState] = mapped_column(
        pg_enum(CardState, name="card_state"),
        default=CardState.NEW,
        nullable=False,
    )
    created_at: Mapped[created_ts]
    updated_at: Mapped[updated_ts]


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (Index("ix_review_user_time", "user_id", "reviewed_at"),)

    id: Mapped[uuid_pk]
    user_card_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_cards.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[ReviewRating] = mapped_column(
        pg_enum(ReviewRating, name="review_rating"),
        nullable=False,
    )
    elapsed_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prev_interval_days: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    new_interval_days: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    reviewed_at: Mapped[created_ts]
