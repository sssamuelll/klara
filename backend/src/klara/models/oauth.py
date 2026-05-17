from fastapi_users_db_sqlalchemy import SQLAlchemyBaseOAuthAccountTableUUID
from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from klara.models.base import Base


class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, Base):
    __tablename__ = "oauth_accounts"

    # Override the inherited FK target. The base class points at the singular
    # table name "user", but Klara's users table is "users" — and the Alembic
    # migration (20260516_0004) already creates the DB-level FK against
    # "users.id", so this rewires only the ORM-level mapping.
    user_id: Mapped[GUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="cascade"), nullable=False
    )
