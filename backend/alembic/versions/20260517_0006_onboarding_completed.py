"""onboarding_completed_at column on users

Revision ID: 20260517_0006
Revises: 20260516_0005
Create Date: 2026-05-17

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260517_0006"
down_revision: str | None = "20260516_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "onboarding_completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "onboarding_completed_at")
