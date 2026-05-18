from typing import TYPE_CHECKING

from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from klara.models.base import Base, created_ts, nullable_ts, pg_enum, updated_ts
from klara.models.enums import CEFRLevel

if TYPE_CHECKING:
    from klara.models.oauth import OAuthAccount


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"

    # Override the FastAPI-Users mixin defaults: email and hashed_password must be
    # nullable so (a) the legacy single-user row can exist with email IS NULL
    # until INITIAL_OWNER_EMAIL claims it, and (b) Google-OAuth-only accounts
    # don't carry a password.
    email: Mapped[str | None] = mapped_column(  # type: ignore[assignment]
        String(320), unique=True, index=True, nullable=True
    )
    hashed_password: Mapped[str | None] = mapped_column(  # type: ignore[assignment]
        String(1024), nullable=True
    )

    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    level: Mapped[CEFRLevel] = mapped_column(
        pg_enum(CEFRLevel, name="cefr_level"),
        default=CEFRLevel.A0,
        nullable=False,
    )
    native_language: Mapped[str] = mapped_column(String(8), default="es", nullable=False)
    target_language: Mapped[str] = mapped_column(String(8), default="de", nullable=False)
    learning_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    onboarding_completed_at: Mapped[nullable_ts]
    created_at: Mapped[created_ts]
    updated_at: Mapped[updated_ts]

    # fastapi-users-db-sqlalchemy's add_oauth_account() does
    # `user.oauth_accounts.append(...)` and get_by_oauth_account() iterates
    # the relationship — both require this attribute. lazy="selectin" so async
    # sessions don't hit MissingGreenlet on implicit lazy loads.
    oauth_accounts: Mapped[list["OAuthAccount"]] = relationship("OAuthAccount", lazy="selectin")
