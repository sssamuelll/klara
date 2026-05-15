from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from german_app.models.base import Base, created_ts, pg_enum, updated_ts, uuid_pk
from german_app.models.enums import CEFRLevel


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid_pk]
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
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
