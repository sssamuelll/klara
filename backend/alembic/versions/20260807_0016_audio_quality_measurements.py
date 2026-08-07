"""audio_quality_measurements — muestra persistente del gate de audio (#120 punto 4)

Revision ID: 20260807_0016
Revises: 20260713_0015
Create Date: 2026-08-07

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260807_0016"
down_revision: str | None = "20260713_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audio_quality_measurements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # source/verdict quedan como String y no como enum pg: son etiquetas de
        # muestreo, y un enum obliga a migración cada vez que aparece un cuarto
        # endpoint con gate. ponytail: promover a enum si algo ramifica sobre
        # ellas en tiempo de ejecución.
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("verdict", sa.String(16), nullable=False),
        sa.Column("reasons", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("voice_ms", sa.Integer(), nullable=False),
        sa.Column("speech_rms_dbfs", sa.Float(), nullable=False),
        sa.Column("clip_rms_dbfs", sa.Float(), nullable=False),
        sa.Column("peak_dbfs", sa.Float(), nullable=False),
        sa.Column("noise_floor_dbfs", sa.Float(), nullable=True),
        sa.Column("snr_db", sa.Float(), nullable=True),
        sa.Column("clipping_ratio", sa.Float(), nullable=False),
        sa.Column("applied_gain_db", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "gain_limited", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("input_speech_rms_dbfs", sa.Float(), nullable=True),
        sa.Column(
            "measured_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_audio_quality_verdict_time",
        "audio_quality_measurements",
        ["verdict", "measured_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_audio_quality_verdict_time", table_name="audio_quality_measurements")
    op.drop_table("audio_quality_measurements")
