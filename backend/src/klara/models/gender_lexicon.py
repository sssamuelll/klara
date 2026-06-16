from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from klara.models.base import Base


class GenderLexicon(Base):
    """Authoritative German noun gender, seeded offline from an open dataset
    (gambolputty/german-nouns, CC-BY-SA 4.0). The curriculum's source of truth
    for der/die/das — never written by the LLM."""

    __tablename__ = "gender_lexicon"
    __table_args__ = (
        CheckConstraint("gender IN ('der', 'die', 'das')", name="ck_gender_lexicon_gender"),
    )

    lemma: Mapped[str] = mapped_column(String(120), primary_key=True)
    pos: Mapped[str] = mapped_column(String(16), default="noun", nullable=False)
    gender: Mapped[str] = mapped_column(String(8), nullable=False)  # der | die | das
