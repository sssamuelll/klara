"""stories.perceived_difficulty — señal de dificultad por tap (consenso 2026-07-13)

Revision ID: 20260713_0015
Revises: 20260703_0014
Create Date: 2026-07-13

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260713_0015"
down_revision: str | None = "20260703_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Free-text-shaped but Literal-validated at the API layer; a pg enum for a
    # 3-value user tap is churn without payoff. ponytail: promote to enum if a
    # second writer ever appears.
    op.add_column("stories", sa.Column("perceived_difficulty", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("stories", "perceived_difficulty")
