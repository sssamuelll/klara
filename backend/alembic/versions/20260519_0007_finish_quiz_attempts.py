"""Finish-quiz items + insight cache on stories + attempt tables

Adds:
- stories.quiz_items (JSONB nullable) — LLM-generated quiz, 4 items.
- stories.insight_title + insight_body — cached linguistic insight.
- pronunciation_attempts — every mic→score round-trip per sentence per
  user. Powers struggled-today tags and the souvenir picker.
- quiz_attempts — every answer/reveal on the Finish quiz.

Revision ID: 20260519_0007
Revises: 20260517_0006
Create Date: 2026-05-19

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "20260519_0007"
down_revision: str | None = "20260517_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("stories", sa.Column("quiz_items", JSONB, nullable=True))
    op.add_column("stories", sa.Column("insight_title", sa.String(200), nullable=True))
    op.add_column("stories", sa.Column("insight_body", sa.String(2000), nullable=True))

    op.create_table(
        "pronunciation_attempts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "story_id",
            UUID(as_uuid=True),
            sa.ForeignKey("stories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sentence_index", sa.Integer, nullable=False),
        sa.Column("reference_text", sa.String(2000), nullable=False),
        sa.Column("recognized_text", sa.String(2000), nullable=True),
        sa.Column("overall_score", sa.Float, nullable=False),
        sa.Column("word_bands", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "attempted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_pron_attempt_user_story",
        "pronunciation_attempts",
        ["user_id", "story_id", "attempted_at"],
    )
    op.create_index(
        "ix_pron_attempt_story_sentence",
        "pronunciation_attempts",
        ["story_id", "sentence_index"],
    )

    op.create_table(
        "quiz_attempts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "story_id",
            UUID(as_uuid=True),
            sa.ForeignKey("stories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question_index", sa.Integer, nullable=False),
        sa.Column("question_type", sa.String(16), nullable=False),
        sa.Column("was_correct", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("was_revealed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("detail", JSONB, nullable=True),
        sa.Column(
            "attempted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_quiz_attempt_user_story",
        "quiz_attempts",
        ["user_id", "story_id", "attempted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_quiz_attempt_user_story", table_name="quiz_attempts")
    op.drop_table("quiz_attempts")
    op.drop_index("ix_pron_attempt_story_sentence", table_name="pronunciation_attempts")
    op.drop_index("ix_pron_attempt_user_story", table_name="pronunciation_attempts")
    op.drop_table("pronunciation_attempts")
    op.drop_column("stories", "insight_body")
    op.drop_column("stories", "insight_title")
    op.drop_column("stories", "quiz_items")
