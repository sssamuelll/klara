from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from klara.models.base import Base


class GenderL1Note(Base):
    """Hand-curated L1 gender-transfer note: for a German lemma and a learner's
    native language, prose explaining the ES<->DE gender clash. Authoritative,
    never written by the LLM. The DE gender is NOT stored here -- it is resolved
    from the oracle (VocabItem.gender, gender_source='oracle') at serve time, so
    this row never holds a der/die/das claim that could drift from the oracle."""

    __tablename__ = "gender_l1_notes"

    lemma: Mapped[str] = mapped_column(String(120), primary_key=True)
    l1_language: Mapped[str] = mapped_column(String(8), primary_key=True)
    note: Mapped[str] = mapped_column(String(400), nullable=False)
