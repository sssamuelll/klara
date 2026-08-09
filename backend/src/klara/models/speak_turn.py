"""One scored Speak turn — the per-turn assessment that used to die in memory.

Issue #127 (D-K clause, 2026-08-09): a signal that was never persisted may be
born as an append-only event table; what already lives in tables is derived,
not duplicated. Speak sessions have no server-side row until /finish, so turns
group under a client-generated UUID (client_session_id) that /finish echoes
into StudySession.wins["session_id"] for linking.

no_speech and low-confidence turns are NOT persisted: a probably-fabricated
transcript is garbage signal for the longitudinal error memory.
"""

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from klara.models.base import Base, created_ts, uuid_pk


class SpeakTurn(Base):
    __tablename__ = "speak_turns"
    __table_args__ = (
        Index("ix_speak_turn_user_time", "user_id", "created_at"),
        Index("ix_speak_turn_user_session", "user_id", "client_session_id"),
    )

    id: Mapped[uuid_pk]
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    client_session_id: Mapped[UUID] = mapped_column(nullable=False)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False)
    focus_sound: Mapped[str] = mapped_column(String(8), nullable=False)
    recognized_text: Mapped[str] = mapped_column(Text, nullable=False)
    #: [{"t": word, "s": "good"|"ok"|"bad", "focus": bool}] — speak_analysis bands.
    tokens: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    #: {"word", "focus_accuracy", "should_ipa"} — worst focus word, or NULL.
    target: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    #: {"accuracy", "fluency", "pronunciation"} — Azure turn-level scores.
    scores: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    focus_hit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    focus_clear: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    retry_word: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[created_ts]
