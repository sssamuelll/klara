"""portadas de historias — subtítulo y escena, y la tabla de ilustraciones

Aditiva. Dos columnas nullable en `stories` y `story_library` (subtitle,
scene) y una tabla nueva, `illustrations`, con una imagen por escena
(spec 2026-09-30-hoy-y-biblioteca §3).

Revision ID: 20260930_0023
Revises: 20260829_0022
Create Date: 2026-09-30

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260930_0023"
down_revision: str | None = "20260829_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLAS = ("stories", "story_library")


def upgrade() -> None:
    for tabla in TABLAS:
        op.add_column(tabla, sa.Column("subtitle", sa.String(160), nullable=True))
        op.add_column(tabla, sa.Column("scene", sa.String(600), nullable=True))
    op.create_table(
        "illustrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("hash", sa.String(64), nullable=False, unique=True),
        sa.Column("scene", sa.Text(), nullable=False),
        sa.Column("style_version", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("mime_type", sa.String(40), nullable=False),
        sa.Column("image_data", sa.LargeBinary(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("illustrations")
    for tabla in TABLAS:
        op.drop_column(tabla, "scene")
        op.drop_column(tabla, "subtitle")
