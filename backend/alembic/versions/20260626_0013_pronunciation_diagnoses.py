"""pronunciation_diagnoses cache + analytics table

Revision ID: 20260626_0013
Revises: 20260622_0012
Create Date: 2026-06-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260626_0013"
down_revision: str | None = "20260622_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pronunciation_diagnoses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("native_language", sa.String(8), nullable=False),
        sa.Column("target_language", sa.String(8), nullable=False),
        sa.Column("word", sa.String(120), nullable=False),
        sa.Column("weakest_phoneme", sa.String(32), nullable=False),
        sa.Column("phoneme_score", sa.Float(), nullable=False),
        sa.Column("tip", sa.String(400), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "native_language", "target_language", "word", "weakest_phoneme",
            name="uq_pron_diag_key",
        ),
    )
    op.create_index(
        "ix_pron_diag_phoneme",
        "pronunciation_diagnoses",
        ["native_language", "target_language", "weakest_phoneme"],
    )


def downgrade() -> None:
    op.drop_index("ix_pron_diag_phoneme", table_name="pronunciation_diagnoses")
    op.drop_table("pronunciation_diagnoses")
