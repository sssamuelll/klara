"""study_cards + study_card_reviews — el taller (F0)

Aditiva: cero cambios sobre tablas existentes. Tablas nuevas a propósito, no una
extensión de user_cards/vocab_items — el aislamiento del dominio de alemán es la
restricción número uno de la fase.

Revision ID: 20260811_0021
Revises: 20260810_0020
Create Date: 2026-08-11

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260811_0021"
down_revision: str | None = "20260810_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CARD_STATE_VALUES = ("new", "learning", "reviewing", "relearning", "suspended")
REVIEW_RATING_VALUES = ("again", "hard", "good", "easy")


def upgrade() -> None:
    # create_type=False: los dos tipos ya existen desde 20260502_0001. Crear un
    # segundo con el mismo nombre revienta el upgrade.
    card_state = postgresql.ENUM(*CARD_STATE_VALUES, name="card_state", create_type=False)
    review_rating = postgresql.ENUM(*REVIEW_RATING_VALUES, name="review_rating", create_type=False)

    op.create_table(
        "study_cards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("front", sa.Text(), nullable=False),
        sa.Column("back", sa.Text(), nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state", card_state, nullable=False, server_default="new"),
        sa.Column("stability", sa.Float(), nullable=True),
        sa.Column("difficulty", sa.Float(), nullable=True),
        sa.Column("fsrs_step", sa.Integer(), nullable=True),
        sa.Column("fsrs_last_review", sa.DateTime(timezone=True), nullable=True),
        sa.Column("interval_days", sa.Float(), nullable=False, server_default="0"),
        # NOT NULL con default now(), a diferencia de user_cards: la tarjeta nace
        # vencida y la cola sale ordenada sin la rama `is_(None)`.
        sa.Column(
            "next_review_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("repetitions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_study_card_due", "study_cards", ["user_id", "next_review_at"])
    op.create_index("ix_study_card_batch", "study_cards", ["user_id", "batch_id"])

    op.create_table(
        "study_card_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "study_card_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("study_cards.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rating", review_rating, nullable=False),
        sa.Column("elapsed_seconds", sa.Integer(), nullable=True),
        sa.Column("prev_interval_days", sa.Float(), nullable=False, server_default="0"),
        sa.Column("new_interval_days", sa.Float(), nullable=False, server_default="0"),
        sa.Column("device", sa.String(16), nullable=False),
        sa.Column(
            "reviewed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("device IN ('desktop', 'mobile')", name="ck_study_review_device"),
    )
    op.create_index("ix_study_review_user_time", "study_card_reviews", ["user_id", "reviewed_at"])


def downgrade() -> None:
    # Los tipos card_state/review_rating NO se tocan: son de user_cards/reviews.
    op.drop_index("ix_study_review_user_time", table_name="study_card_reviews")
    op.drop_table("study_card_reviews")
    op.drop_index("ix_study_card_batch", table_name="study_cards")
    op.drop_index("ix_study_card_due", table_name="study_cards")
    op.drop_table("study_cards")
