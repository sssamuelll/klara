from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from german_app.models.base import Base, created_ts, pg_enum, uuid_pk
from german_app.models.enums import SessionType


class StudySession(Base):
    __tablename__ = "study_sessions"
    __table_args__ = (Index("ix_study_session_user_time", "user_id", "started_at"),)

    id: Mapped[uuid_pk]
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_type: Mapped[SessionType] = mapped_column(
        pg_enum(SessionType, name="session_type"),
        default=SessionType.STORY,
        nullable=False,
    )
    started_at: Mapped[created_ts]
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    wins: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
