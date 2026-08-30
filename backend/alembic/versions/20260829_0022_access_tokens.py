"""access_tokens — sesiones Bearer revocables del app nativo (F-A0)

Aditiva. Tabla nueva; cero cambios sobre tablas existentes. El transporte de
cookie sigue intacto: esta tabla solo la usa el backend "bearer-db".

Revision ID: 20260829_0022
Revises: 20260811_0021
Create Date: 2026-08-29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260829_0022"
down_revision: str | None = "20260811_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "access_tokens",
        sa.Column("token", sa.String(length=43), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    # El nombre coincide con el que genera `index=True` de la clase base, así
    # el autogenerate de alembic no ve deriva.
    op.create_index("ix_access_tokens_created_at", "access_tokens", ["created_at"])
    op.create_index("ix_access_tokens_user_id", "access_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_access_tokens_user_id", table_name="access_tokens")
    op.drop_index("ix_access_tokens_created_at", table_name="access_tokens")
    op.drop_table("access_tokens")
