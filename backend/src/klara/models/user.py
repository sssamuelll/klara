from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from klara.models.base import Base, created_ts, pg_enum, updated_ts
from klara.models.enums import CEFRLevel


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
    created_at: Mapped[created_ts]
    updated_at: Mapped[updated_ts]
