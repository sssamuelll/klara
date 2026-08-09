"""fsrs_columns — estado FSRS en user_cards + canal en reviews (#125)

El motor de recall pasa de SM-2 lite a FSRS: user_cards gana las 4 columnas
de estado (stability/difficulty/fsrs_step/fsrs_last_review, nullable) y
reviews gana el discriminador de canal (recall vs pronunciation). El backfill
replay-ea el ledger histórico vía reschedule_card SIN tocar los campos
operativos (transición gradual, default de fsrs4anki).

Revision ID: 20260809_0018
Revises: 20260809_0017
Create Date: 2026-08-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.orm import Session

from alembic import op

revision: str = "20260809_0018"
down_revision: str | None = "20260809_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user_cards", sa.Column("stability", sa.Float(), nullable=True))
    op.add_column("user_cards", sa.Column("difficulty", sa.Float(), nullable=True))
    op.add_column("user_cards", sa.Column("fsrs_step", sa.Integer(), nullable=True))
    op.add_column(
        "user_cards",
        sa.Column("fsrs_last_review", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "reviews",
        sa.Column("channel", sa.String(16), nullable=False, server_default="recall"),
    )

    # El env de alembic ya importa klara.models; esta migración es head, el
    # esquema coincide con los modelos.
    from klara.services.srs_backfill import backfill_fsrs_state

    backfill_fsrs_state(Session(bind=op.get_bind()))


def downgrade() -> None:
    op.drop_column("reviews", "channel")
    op.drop_column("user_cards", "fsrs_last_review")
    op.drop_column("user_cards", "fsrs_step")
    op.drop_column("user_cards", "difficulty")
    op.drop_column("user_cards", "stability")
