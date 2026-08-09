"""speak_turns — persistencia por turno del assessment de Speak (#127)

La señal por turno moría en memoria (solo el resumen llegaba a
study_sessions.wins). Cláusula D-K 2026-08-09: una señal que nunca se
persistió puede nacer como tabla de eventos append-only.

Revision ID: 20260809_0017
Revises: 20260807_0016
Create Date: 2026-08-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260809_0017"
down_revision: str | None = "20260807_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "speak_turns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Identidad de sesión generada por el cliente: no hay fila de sesión
        # server-side hasta /finish, así que no puede ser FK.
        sa.Column("client_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(8), nullable=False),
        sa.Column("focus_sound", sa.String(8), nullable=False),
        sa.Column("recognized_text", sa.Text(), nullable=False),
        sa.Column("tokens", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("target", postgresql.JSONB(), nullable=True),
        sa.Column("scores", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "focus_hit", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "focus_clear", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("retry_word", sa.String(40), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_speak_turn_user_time", "speak_turns", ["user_id", "created_at"])
    op.create_index(
        "ix_speak_turn_user_session", "speak_turns", ["user_id", "client_session_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_speak_turn_user_session", table_name="speak_turns")
    op.drop_index("ix_speak_turn_user_time", table_name="speak_turns")
    op.drop_table("speak_turns")
