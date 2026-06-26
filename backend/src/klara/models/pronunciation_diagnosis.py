"""LLM-authored corrective pronunciation tip for one (L1, target, word, weakest IPA phoneme).

Doubles as the cache (skip the LLM on a seen key) and the analytics log
(hit_count → which phonemes a given L1 fails most). Language-pair-keyed, not
per-user: a tip is a fact about a sound clash, not about a person.
"""

from __future__ import annotations

from sqlalchemy import Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from klara.models.base import Base, created_ts, updated_ts, uuid_pk


class PronunciationDiagnosis(Base):
    __tablename__ = "pronunciation_diagnoses"
    __table_args__ = (
        UniqueConstraint(
            "native_language",
            "target_language",
            "word",
            "weakest_phoneme",
            name="uq_pron_diag_key",
        ),
        Index("ix_pron_diag_phoneme", "native_language", "target_language", "weakest_phoneme"),
    )

    id: Mapped[uuid_pk]
    native_language: Mapped[str] = mapped_column(String(8), nullable=False)
    target_language: Mapped[str] = mapped_column(String(8), nullable=False)
    word: Mapped[str] = mapped_column(String(120), nullable=False)  # canonical lower-cased key
    weakest_phoneme: Mapped[str] = mapped_column(String(32), nullable=False)
    phoneme_score: Mapped[float] = mapped_column(Float, nullable=False)
    tip: Mapped[str] = mapped_column(String(400), nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[created_ts]
    updated_at: Mapped[updated_ts]
