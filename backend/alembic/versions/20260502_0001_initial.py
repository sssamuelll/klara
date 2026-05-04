"""initial schema

Revision ID: 20260502_0001
Revises:
Create Date: 2026-05-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260502_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CEFR_VALUES = ("A0", "A1", "A2", "B1", "B2", "C1")
POS_VALUES = (
    "noun", "verb", "adjective", "adverb", "pronoun",
    "preposition", "conjunction", "article", "phrase", "other",
)
CARD_STATE_VALUES = ("new", "learning", "reviewing", "relearning", "suspended")
REVIEW_RATING_VALUES = ("again", "hard", "good", "easy")
SESSION_TYPE_VALUES = ("story", "review", "chat", "mixed")


def upgrade() -> None:
    cefr_level = postgresql.ENUM(*CEFR_VALUES, name="cefr_level", create_type=False)
    pos = postgresql.ENUM(*POS_VALUES, name="part_of_speech", create_type=False)
    card_state = postgresql.ENUM(*CARD_STATE_VALUES, name="card_state", create_type=False)
    review_rating = postgresql.ENUM(*REVIEW_RATING_VALUES, name="review_rating", create_type=False)
    session_type = postgresql.ENUM(*SESSION_TYPE_VALUES, name="session_type", create_type=False)

    bind = op.get_bind()
    for enum in (cefr_level, pos, card_state, review_rating, session_type):
        enum.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("level", cefr_level, nullable=False, server_default="A0"),
        sa.Column("native_language", sa.String(8), nullable=False, server_default="es"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "vocab_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("language", sa.String(8), nullable=False, server_default="de"),
        sa.Column("lemma", sa.String(120), nullable=False),
        sa.Column("pos", pos, nullable=False, server_default="other"),
        sa.Column("gender", sa.String(8), nullable=True),
        sa.Column("plural", sa.String(120), nullable=True),
        sa.Column("translation_es", sa.String(255), nullable=True),
        sa.Column("translation_en", sa.String(255), nullable=True),
        sa.Column("example_de", sa.String(500), nullable=True),
        sa.Column("example_es", sa.String(500), nullable=True),
        sa.Column("ipa", sa.String(120), nullable=True),
        sa.Column("cefr_level", cefr_level, nullable=True),
        sa.Column("frequency_rank", sa.Integer(), nullable=True),
        sa.Column("audio_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("lemma", "language", "pos", name="uq_vocab_lemma_lang_pos"),
    )
    op.create_index("ix_vocab_cefr_freq", "vocab_items", ["cefr_level", "frequency_rank"])

    op.create_table(
        "user_cards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vocab_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vocab_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ease", sa.Float(), nullable=False, server_default="2.5"),
        sa.Column("interval_days", sa.Float(), nullable=False, server_default="0"),
        sa.Column("repetitions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state", card_state, nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "vocab_item_id", name="uq_user_card_user_vocab"),
    )
    op.create_index("ix_user_card_due", "user_cards", ["user_id", "next_review_at"])

    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_card_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_cards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rating", review_rating, nullable=False),
        sa.Column("elapsed_seconds", sa.Integer(), nullable=True),
        sa.Column("prev_interval_days", sa.Float(), nullable=False, server_default="0"),
        sa.Column("new_interval_days", sa.Float(), nullable=False, server_default="0"),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_review_user_time", "reviews", ["user_id", "reviewed_at"])

    op.create_table(
        "stories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("level", cefr_level, nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column(
            "target_vocab_item_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("'{}'::uuid[]"),
        ),
        sa.Column("generated_by_provider", sa.String(50), nullable=True),
        sa.Column("generated_by_model", sa.String(120), nullable=True),
        sa.Column("generation_cost_usd", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_story_user_created", "stories", ["user_id", "created_at"])

    op.create_table(
        "story_views",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("comprehension_score", sa.Float(), nullable=True),
    )
    op.create_index("ix_story_view_user", "story_views", ["user_id", "started_at"])

    op.create_table(
        "study_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_type", session_type, nullable=False, server_default="story"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("wins", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_study_session_user_time", "study_sessions", ["user_id", "started_at"])


def downgrade() -> None:
    op.drop_index("ix_study_session_user_time", table_name="study_sessions")
    op.drop_table("study_sessions")
    op.drop_index("ix_story_view_user", table_name="story_views")
    op.drop_table("story_views")
    op.drop_index("ix_story_user_created", table_name="stories")
    op.drop_table("stories")
    op.drop_index("ix_review_user_time", table_name="reviews")
    op.drop_table("reviews")
    op.drop_index("ix_user_card_due", table_name="user_cards")
    op.drop_table("user_cards")
    op.drop_index("ix_vocab_cefr_freq", table_name="vocab_items")
    op.drop_table("vocab_items")
    op.drop_table("users")

    bind = op.get_bind()
    for name in ("session_type", "review_rating", "card_state", "part_of_speech", "cefr_level"):
        sa.Enum(name=name).drop(bind, checkfirst=True)
