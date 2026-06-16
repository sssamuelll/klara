"""modules + module_vocab + users.current_module_id

Revision ID: 20260616_0009
Revises: 20260520_0008
Create Date: 2026-06-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "20260616_0009"
down_revision: str | None = "20260520_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Reference the EXISTING cefr_level enum — create_type=False so the migration
# never tries to CREATE TYPE (it already exists from the initial migration).
cefr_level = PG_ENUM(
    "A0", "A1", "A2", "B1", "B2", "C1", name="cefr_level", create_type=False
)


def upgrade() -> None:
    op.create_table(
        "modules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("language", sa.String(8), nullable=False),
        sa.Column("cefr_level", cefr_level, nullable=False),
        sa.Column("sequence_order", sa.Integer, nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("can_dos", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column(
            "grammatical_focus", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("mastery_threshold", sa.Float, nullable=False, server_default=sa.text("0.85")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("language", "sequence_order", name="uq_module_lang_seq"),
    )
    op.create_table(
        "module_vocab",
        sa.Column(
            "module_id",
            UUID(as_uuid=True),
            sa.ForeignKey("modules.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "vocab_item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("vocab_items.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "current_module_id",
            UUID(as_uuid=True),
            sa.ForeignKey("modules.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    # Reverse dependency order: drop the FK column on users first, then the
    # association, then modules. Do NOT drop the shared cefr_level enum.
    op.drop_column("users", "current_module_id")
    op.drop_table("module_vocab")
    op.drop_table("modules")
