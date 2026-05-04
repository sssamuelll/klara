"""audio cache table

Revision ID: 20260502_0002
Revises: 20260502_0001
Create Date: 2026-05-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260502_0002"
down_revision: Union[str, None] = "20260502_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audio_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("text_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("voice_id", sa.String(80), nullable=False),
        sa.Column("mime_type", sa.String(40), nullable=False, server_default="audio/mpeg"),
        sa.Column("audio_data", sa.LargeBinary(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("access_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audio_cache_last_access", "audio_cache", ["last_accessed_at"])


def downgrade() -> None:
    op.drop_index("ix_audio_cache_last_access", table_name="audio_cache")
    op.drop_table("audio_cache")
