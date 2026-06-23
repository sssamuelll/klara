from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from klara.models.base import Base, created_ts, uuid_pk


class GenderAttempt(Base):
    """Diadic gender evidence: which article the user picked for a given noun,
    and whether it matched the oracle. The per-noun binding `assigns(user, noun,
    article)` — deliberately NOT folded into the monadic UserCard (lexical SRS).
    A future is_mastered_gender derives mastery from these rows."""

    __tablename__ = "gender_attempts"
    __table_args__ = (
        Index("ix_gender_attempt_user_vocab", "user_id", "vocab_item_id"),
        CheckConstraint("picked_article IN ('der', 'die', 'das')", name="ck_gender_attempt_picked"),
    )

    id: Mapped[uuid_pk]
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    vocab_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("vocab_items.id", ondelete="CASCADE"), nullable=False
    )
    picked_article: Mapped[str] = mapped_column(String(8), nullable=False)  # der | die | das
    was_correct: Mapped[bool] = mapped_column(nullable=False)
    # Reconciled suffix-rule detail (the 6-key GenderRuleDetail) written by
    # grade_gender_attempt; read by the Case-B audit. Null when no suffix matched.
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    attempted_at: Mapped[created_ts]
