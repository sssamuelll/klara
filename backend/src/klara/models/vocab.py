from sqlalchemy import Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from klara.models.base import Base, created_ts, pg_enum, uuid_pk
from klara.models.enums import CEFRLevel, PartOfSpeech


class VocabItem(Base):
    __tablename__ = "vocab_items"
    __table_args__ = (
        UniqueConstraint("lemma", "language", "pos", name="uq_vocab_lemma_lang_pos"),
        Index("ix_vocab_cefr_freq", "cefr_level", "frequency_rank"),
    )

    id: Mapped[uuid_pk]
    language: Mapped[str] = mapped_column(String(8), default="de", nullable=False)
    lemma: Mapped[str] = mapped_column(String(120), nullable=False)
    pos: Mapped[PartOfSpeech] = mapped_column(
        pg_enum(PartOfSpeech, name="part_of_speech"),
        default=PartOfSpeech.OTHER,
        nullable=False,
    )
    gender: Mapped[str | None] = mapped_column(String(8), nullable=True)
    gender_source: Mapped[str] = mapped_column(
        String(8), server_default="llm", default="llm", nullable=False
    )  # oracle | llm | user
    plural: Mapped[str | None] = mapped_column(String(120), nullable=True)
    translations: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    example_target: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ipa: Mapped[str | None] = mapped_column(String(120), nullable=True)
    cefr_level: Mapped[CEFRLevel | None] = mapped_column(
        pg_enum(CEFRLevel, name="cefr_level", create_type=False),
        nullable=True,
    )
    frequency_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    audio_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[created_ts]
