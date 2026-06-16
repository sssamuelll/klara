"""gender_attempts evidence table

Revision ID: 20260616_0011
Revises: 20260616_0010
Create Date: 2026-06-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "20260616_0011"
down_revision: str | None = "20260616_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gender_attempts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "vocab_item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("vocab_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("picked_article", sa.String(8), nullable=False),
        sa.Column("was_correct", sa.Boolean, nullable=False),
        sa.Column("detail", JSONB, nullable=True),
        sa.Column(
            "attempted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "picked_article IN ('der', 'die', 'das')", name="ck_gender_attempt_picked"
        ),
    )
    op.create_index("ix_gender_attempt_user_vocab", "gender_attempts", ["user_id", "vocab_item_id"])


def downgrade() -> None:
    op.drop_index("ix_gender_attempt_user_vocab", table_name="gender_attempts")
    op.drop_table("gender_attempts")
