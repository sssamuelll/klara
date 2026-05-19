"""Per-attempt records for what the user actually did during a story.

Drives:
- "Struggled today" tags in the Finish summary (which words / sentences
  scored poorly in this session).
- The souvenir line picker — favour sentences the user nailed.
- Future analytics + SRS personalisation (words tied to repeatedly-bad
  attempts get scheduled more aggressively).

Two row types, one per concrete action:

- `PronunciationAttempt` — every time the mic produces a score for a
  specific sentence of a specific story. Many per session per sentence
  (the user can retry).
- `QuizAttempt` — every time the user answers a question on the Finish
  quiz (or reveals it). One per question per pass through Finish.
"""

from uuid import UUID

from sqlalchemy import Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from klara.models.base import Base, created_ts, uuid_pk


class PronunciationAttempt(Base):
    """Records one mic→score round-trip for a story sentence."""

    __tablename__ = "pronunciation_attempts"
    __table_args__ = (
        Index("ix_pron_attempt_user_story", "user_id", "story_id", "attempted_at"),
        Index("ix_pron_attempt_story_sentence", "story_id", "sentence_index"),
    )

    id: Mapped[uuid_pk]
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    story_id: Mapped[UUID] = mapped_column(
        ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    sentence_index: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_text: Mapped[str] = mapped_column(String(2000), nullable=False)
    recognized_text: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    # Azure's overall pronunciation score (0-100), the headline number.
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    # Per-word bands keyed by full token index, e.g. {"0": "good", "2": "bad"}.
    # Stored as JSONB so future variants (IPA, finer bands) don't require migrations.
    word_bands: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    attempted_at: Mapped[created_ts]


class QuizAttempt(Base):
    """Records one answer (or reveal) on a Finish quiz item."""

    __tablename__ = "quiz_attempts"
    __table_args__ = (Index("ix_quiz_attempt_user_story", "user_id", "story_id", "attempted_at"),)

    id: Mapped[uuid_pk]
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    story_id: Mapped[UUID] = mapped_column(
        ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    question_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # "mc" | "cloze" | "shadow" — kept as plain string (no enum) so the
    # quiz_items shape can grow new types without schema churn.
    question_type: Mapped[str] = mapped_column(String(16), nullable=False)
    was_correct: Mapped[bool] = mapped_column(nullable=False, default=False)
    was_revealed: Mapped[bool] = mapped_column(nullable=False, default=False)
    # Optional payload — for shadow/cloze this is the per-token bands or the
    # picked option index; the orchestrator decides what's useful to keep.
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    attempted_at: Mapped[created_ts]
