from sqlalchemy import Column, Float, ForeignKey, Integer, String, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from klara.models.base import Base, created_ts, pg_enum, uuid_pk
from klara.models.enums import CEFRLevel
from klara.models.vocab import VocabItem

# Association: a module's curated vocab microlist. Cascade so dropping a module
# (or a vocab item) cleans its links without orphaning rows.
module_vocab = Table(
    "module_vocab",
    Base.metadata,
    Column(
        "module_id",
        PGUUID(as_uuid=True),
        ForeignKey("modules.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "vocab_item_id",
        PGUUID(as_uuid=True),
        ForeignKey("vocab_items.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Module(Base):
    """A curriculum unit defined by INTENSION (objectives), never a container of
    stories. Content is conditioned by the module and verified against it; the
    module never references a Story."""

    __tablename__ = "modules"
    __table_args__ = (UniqueConstraint("language", "sequence_order", name="uq_module_lang_seq"),)

    id: Mapped[uuid_pk]
    language: Mapped[str] = mapped_column(String(8), nullable=False)
    cefr_level: Mapped[CEFRLevel] = mapped_column(
        pg_enum(CEFRLevel, name="cefr_level", create_type=False), nullable=False
    )
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    can_dos: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    grammatical_focus: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    mastery_threshold: Mapped[float] = mapped_column(Float, default=0.85, nullable=False)
    created_at: Mapped[created_ts]

    vocab_items: Mapped[list[VocabItem]] = relationship(secondary=module_vocab, lazy="selectin")
