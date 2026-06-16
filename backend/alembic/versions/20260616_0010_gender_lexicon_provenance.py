"""gender_lexicon oracle table + vocab_items.gender_source

Revision ID: 20260616_0010
Revises: 20260616_0009
Create Date: 2026-06-16

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260616_0010"
down_revision: str | None = "20260616_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gender_lexicon",
        sa.Column("lemma", sa.String(120), primary_key=True),
        sa.Column("pos", sa.String(16), nullable=False, server_default="noun"),
        sa.Column("gender", sa.String(8), nullable=False),
        sa.CheckConstraint("gender IN ('der', 'die', 'das')", name="ck_gender_lexicon_gender"),
    )
    op.add_column(
        "vocab_items",
        sa.Column("gender_source", sa.String(8), nullable=False, server_default="llm"),
    )
    op.create_check_constraint(
        "ck_vocab_gender_source", "vocab_items", "gender_source IN ('oracle', 'llm', 'user')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_vocab_gender_source", "vocab_items", type_="check")
    op.drop_column("vocab_items", "gender_source")
    op.drop_table("gender_lexicon")  # the table-level CHECK drops with the table
