"""klara_note column on stories — Finish summary teaser cache.

Revision ID: 20260520_0008
Revises: 20260519_0007
Create Date: 2026-05-20

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260520_0008"
down_revision: str | None = "20260519_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("stories", sa.Column("klara_note", sa.String(400), nullable=True))


def downgrade() -> None:
    op.drop_column("stories", "klara_note")
