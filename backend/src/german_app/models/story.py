from datetime import datetime
from uuid import UUID

from sqlalchemy import ARRAY, DateTime, Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from german_app.models.base import Base, created_ts, pg_enum, uuid_pk
from german_app.models.enums import CEFRLevel


class Story(Base):
    __tablename__ = "stories"
    __table_args__ = (Index("ix_story_user_created", "user_id", "created_at"),)

    id: Mapped[uuid_pk]
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    level: Mapped[CEFRLevel] = mapped_column(
        pg_enum(CEFRLevel, name="cefr_level", create_type=False),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    target_vocab_item_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(PGUUID(as_uuid=True)),
        default=list,
        nullable=False,
    )
    generated_by_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    generated_by_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    generation_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[created_ts]


class StoryView(Base):
    __tablename__ = "story_views"
    __table_args__ = (Index("ix_story_view_user", "user_id", "started_at"),)

    id: Mapped[uuid_pk]
    story_id: Mapped[UUID] = mapped_column(
        ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[created_ts]
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    comprehension_score: Mapped[float | None] = mapped_column(Float, nullable=True)
