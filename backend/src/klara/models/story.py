from datetime import datetime
from uuid import UUID

from sqlalchemy import ARRAY, DateTime, Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from klara.models.base import Base, created_ts, pg_enum, uuid_pk
from klara.models.enums import CEFRLevel


class Story(Base):
    __tablename__ = "stories"
    __table_args__ = (
        Index("ix_story_user_created", "user_id", "created_at"),
        Index("ix_story_user_module", "user_id", "module_id"),
    )

    id: Mapped[uuid_pk]
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    level: Mapped[CEFRLevel] = mapped_column(
        pg_enum(CEFRLevel, name="cefr_level", create_type=False),
        nullable=False,
    )
    target_language: Mapped[str] = mapped_column(String(8), nullable=False)
    native_language: Mapped[str] = mapped_column(String(8), nullable=False)
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
    # Provenance: which module conditioned this story (Story→Module — the June
    # invariant forbids the opposite direction). Basis for "N stories of this
    # module finished". NULL for pre-path stories and module-less generation.
    module_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("modules.id", ondelete="SET NULL"), nullable=True
    )
    # Which library entry this story was claimed from; doubles as the
    # "don't re-serve this entry to this user" filter.
    library_source_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("story_library.id", ondelete="SET NULL"), nullable=True
    )
    # Finish-quiz items, persisted with the story so re-reads quiz on the
    # same questions (testing recall on the same prompts is the whole point
    # of SRS). Shape: [{type, ...}, ...], 4 entries, mixed types. Nullable
    # for backwards compat — stories generated before this column existed
    # backfill lazily via the quiz endpoint.
    quiz_items: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    # Linguistic insight surfaced on the Finish summary. Cached so re-views
    # are free. Title is short ("La tilde de «autobús»"), body is a paragraph
    # explaining the rule, both in the user's native_language.
    insight_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    insight_body: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    # One-line teaser (italic, signed K) shown at the bottom of the Finish
    # summary, previewing tomorrow's lesson at a tonal/level register. The
    # next story isn't pre-generated; this is a vibe-set, not a spoiler.
    klara_note: Mapped[str | None] = mapped_column(String(400), nullable=True)
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
