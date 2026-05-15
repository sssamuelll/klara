"""auth: hashed_password + is_active/verified/superuser + oauth_accounts

Revision ID: 20260516_0004
Revises: 20260515_0003
Create Date: 2026-05-16

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260516_0004"
down_revision: str | None = "20260515_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- users ---------------------------------------------------------------
    # Widen email to FastAPI-Users' standard 320 chars (RFC 5321 max).
    op.alter_column(
        "users",
        "email",
        existing_type=sa.String(255),
        type_=sa.String(320),
        existing_nullable=True,
    )

    # Auth columns: backfill existing legacy row with safe defaults.
    op.add_column(
        "users",
        sa.Column("hashed_password", sa.String(1024), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "users",
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "users",
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # Case-insensitive unique index on email so 'Sam@x.com' and 'sam@x.com'
    # don't collide on signup. Restricted to non-null rows so the legacy
    # row (email IS NULL) coexists until adoption.
    op.create_index(
        "ix_users_email_lower",
        "users",
        [sa.text("lower(email)")],
        unique=True,
        postgresql_where=sa.text("email IS NOT NULL"),
    )

    # --- oauth_accounts ------------------------------------------------------
    op.create_table(
        "oauth_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("oauth_name", sa.String(100), nullable=False),
        sa.Column("access_token", sa.String(1024), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=True),
        sa.Column("refresh_token", sa.String(1024), nullable=True),
        sa.Column("account_id", sa.String(320), nullable=False),
        sa.Column("account_email", sa.String(320), nullable=False),
    )
    op.create_index(
        "ix_oauth_accounts_oauth_account",
        "oauth_accounts",
        ["oauth_name", "account_id"],
        unique=True,
    )
    op.create_index(
        "ix_oauth_accounts_user_id",
        "oauth_accounts",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_oauth_accounts_user_id", table_name="oauth_accounts")
    op.drop_index("ix_oauth_accounts_oauth_account", table_name="oauth_accounts")
    op.drop_table("oauth_accounts")

    op.drop_index("ix_users_email_lower", table_name="users")
    op.drop_column("users", "is_superuser")
    op.drop_column("users", "is_verified")
    op.drop_column("users", "is_active")
    op.drop_column("users", "hashed_password")

    op.alter_column(
        "users",
        "email",
        existing_type=sa.String(320),
        type_=sa.String(255),
        existing_nullable=True,
    )
