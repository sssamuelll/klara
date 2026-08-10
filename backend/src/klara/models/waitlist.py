from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from klara.models.base import Base, created_ts, uuid_pk


class WaitlistSignup(Base):
    __tablename__ = "waitlist_signups"

    id: Mapped[uuid_pk]
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    locale: Mapped[str | None] = mapped_column(String(8), nullable=True)
    created_at: Mapped[created_ts]
    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
