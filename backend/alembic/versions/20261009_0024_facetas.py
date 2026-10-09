"""facetas: estado FSRS por faceta, evidencias y corridas del reproductor

Aditiva (spec 2026-10-09-klara-tres-idiomas §2.2): tres tablas nuevas y la
columna `users.study_languages`.

Revision ID: 20261009_0024
Revises: 20260930_0023
Create Date: 2026-10-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261009_0024"
down_revision: str | None = "20260930_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CARD_STATE_VALUES = ("new", "learning", "reviewing", "relearning", "suspended")
REVIEW_RATING_VALUES = ("again", "hard", "good", "easy")


def _ahora(nombre: str) -> sa.Column:
    return sa.Column(
        nombre, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def _usuario() -> sa.Column:
    return sa.Column(
        "user_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )


def upgrade() -> None:
    # create_type=False: los dos tipos existen desde 20260502_0001.
    card_state = postgresql.ENUM(*CARD_STATE_VALUES, name="card_state", create_type=False)
    review_rating = postgresql.ENUM(*REVIEW_RATING_VALUES, name="review_rating", create_type=False)

    op.add_column(
        "users", sa.Column("study_languages", postgresql.ARRAY(sa.String(5)), nullable=True)
    )

    op.create_table(
        "lesson_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _usuario(),
        sa.Column("idioma", sa.String(5), nullable=False),
        sa.Column("leccion_id", sa.String(80), nullable=True),
        sa.Column("origen", sa.String(8), nullable=False),
        sa.Column("repasos", sa.Integer(), nullable=False, server_default="0"),
        _ahora("started_at"),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("origen IN ('hoy', 'mapa')", name="ck_lesson_run_origen"),
    )
    op.create_index("ix_lesson_run_user", "lesson_runs", ["user_id", "idioma", "finished_at"])

    op.create_table(
        "user_facets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _usuario(),
        sa.Column("idioma", sa.String(5), nullable=False),
        sa.Column("item_key", sa.Text(), nullable=False),
        sa.Column("faceta", sa.String(20), nullable=False),
        sa.Column("state", card_state, nullable=False, server_default="new"),
        sa.Column("stability", sa.Float(), nullable=True),
        sa.Column("difficulty", sa.Float(), nullable=True),
        sa.Column("fsrs_step", sa.Integer(), nullable=True),
        sa.Column("fsrs_last_review", sa.DateTime(timezone=True), nullable=True),
        sa.Column("interval_days", sa.Float(), nullable=False, server_default="0"),
        _ahora("next_review_at"),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("repetitions", sa.Integer(), nullable=False, server_default="0"),
        _ahora("created_at"),
        _ahora("updated_at"),
        sa.UniqueConstraint("user_id", "item_key", "faceta", name="uq_user_facet"),
    )
    op.create_index("ix_user_facet_due", "user_facets", ["user_id", "idioma", "next_review_at"])

    op.create_table(
        "facet_reviews",
        # Sin default: el id lo genera el teléfono y es la clave de idempotencia.
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _usuario(),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("lesson_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("idioma", sa.String(5), nullable=False),
        sa.Column("item_key", sa.Text(), nullable=False),
        sa.Column("faceta", sa.String(20), nullable=False),
        sa.Column("dinamica", sa.String(30), nullable=False),
        sa.Column("modo", sa.String(12), nullable=False),
        sa.Column("acierto", sa.Boolean(), nullable=False),
        sa.Column("pistas", sa.Integer(), nullable=False),
        sa.Column("ms", sa.Integer(), nullable=False),
        sa.Column("nota", review_rating, nullable=True),
        sa.Column("detalle", postgresql.JSONB(), nullable=True),
        _ahora("created_at"),
        sa.CheckConstraint(
            "modo IN ('presentar', 'practicar', 'comprobar')", name="ck_facet_review_modo"
        ),
    )
    op.create_index("ix_facet_review_user_time", "facet_reviews", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_facet_review_user_time", table_name="facet_reviews")
    op.drop_table("facet_reviews")
    op.drop_index("ix_user_facet_due", table_name="user_facets")
    op.drop_table("user_facets")
    op.drop_index("ix_lesson_run_user", table_name="lesson_runs")
    op.drop_table("lesson_runs")
    op.drop_column("users", "study_languages")
