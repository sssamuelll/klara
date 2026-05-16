from sqlalchemy import Index, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from klara.models.base import Base, created_ts, updated_ts, uuid_pk


class AudioCache(Base):
    __tablename__ = "audio_cache"
    __table_args__ = (Index("ix_audio_cache_last_access", "last_accessed_at"),)

    id: Mapped[uuid_pk]
    text_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    voice_id: Mapped[str] = mapped_column(String(80), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(40), nullable=False, default="audio/mpeg")
    audio_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[created_ts]
    last_accessed_at: Mapped[updated_ts]
