"""story_library + stories.module_id/library_source_id

Revision ID: 20260703_0010
Revises: 20260626_0013
Create Date: 2026-07-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM

from alembic import op

revision: str = "20260703_0010"
down_revision: str | None = "20260626_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

cefr_level = PG_ENUM("A0", "A1", "A2", "B1", "B2", "C1", name="cefr_level", create_type=False)


def upgrade() -> None:
    op.create_table(
        "story_library",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "module_id",
            UUID(as_uuid=True),
            sa.ForeignKey("modules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("language", sa.String(8), nullable=False),
        sa.Column("native_language", sa.String(8), nullable=False),
        sa.Column("level", cefr_level, nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", JSONB, nullable=False),
        sa.Column(
            "target_vocab_item_ids",
            ARRAY(UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("'{}'::uuid[]"),
        ),
        sa.Column("quiz_items", JSONB, nullable=True),
        sa.Column("insight_title", sa.String(200), nullable=True),
        sa.Column("insight_body", sa.String(2000), nullable=True),
        sa.Column("topic", sa.String(200), nullable=True),
        sa.Column("source", sa.String(8), nullable=False),
        sa.Column(
            "source_story_id",
            UUID(as_uuid=True),
            sa.ForeignKey("stories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("content_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("times_served", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("generated_by_provider", sa.String(50), nullable=True),
        sa.Column("generated_by_model", sa.String(120), nullable=True),
        sa.Column("generation_cost_usd", sa.Float, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_library_module_native", "story_library", ["module_id", "native_language", "is_active"]
    )
    op.add_column(
        "stories",
        sa.Column(
            "module_id",
            UUID(as_uuid=True),
            sa.ForeignKey("modules.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "stories",
        sa.Column(
            "library_source_id",
            UUID(as_uuid=True),
            sa.ForeignKey("story_library.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_story_user_module", "stories", ["user_id", "module_id"])


def downgrade() -> None:
    op.drop_index("ix_story_user_module", table_name="stories")
    op.drop_column("stories", "library_source_id")
    op.drop_column("stories", "module_id")
    op.drop_index("ix_library_module_native", table_name="story_library")
    op.drop_table("story_library")
