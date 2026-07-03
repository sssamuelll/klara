"""Shared per-module story catalog, served by copy-on-claim (spec 2026-07-03).

NOT a container relationship: Module never references this table; the library
references the module. Claiming clones a row into `stories`, so downstream
flows (finish, quiz, SRS, attempts) never see a library row."""

from uuid import UUID

from sqlalchemy import ARRAY, Boolean, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from klara.models.base import Base, created_ts, pg_enum, uuid_pk
from klara.models.enums import CEFRLevel


class StoryLibrary(Base):
    __tablename__ = "story_library"
    __table_args__ = (
        Index("ix_library_module_native", "module_id", "native_language", "is_active"),
    )

    id: Mapped[uuid_pk]
    module_id: Mapped[UUID] = mapped_column(
        ForeignKey("modules.id", ondelete="CASCADE"), nullable=False
    )
    language: Mapped[str] = mapped_column(String(8), nullable=False)
    native_language: Mapped[str] = mapped_column(String(8), nullable=False)
    level: Mapped[CEFRLevel] = mapped_column(
        pg_enum(CEFRLevel, name="cefr_level", create_type=False), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    target_vocab_item_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(PGUUID(as_uuid=True)), default=list, nullable=False
    )
    quiz_items: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    insight_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    insight_body: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    topic: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # 'seed' (curated batch) | 'pool' (recycled live generation). Plain string,
    # not a PG enum — two values don't earn a type. ponytail: string, enum if a
    # third source ever appears.
    source: Mapped[str] = mapped_column(String(8), nullable=False)
    source_story_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("stories.id", ondelete="SET NULL"), nullable=True
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    times_served: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    generated_by_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    generated_by_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    generation_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[created_ts]
