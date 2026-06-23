"""Canonical gender-eligibility predicate.

A noun is "gender-gradable" iff it is a German NOUN whose gender is
oracle-sourced and one of der/die/das. This predicate was hand-copied across
several read sites; this module is the single source of truth they share.
"""

from __future__ import annotations

from klara.models import VocabItem
from klara.models.enums import PartOfSpeech

GENDER_ARTICLES: tuple[str, ...] = ("der", "die", "das")


def is_gender_eligible(w: VocabItem) -> bool:
    """In-memory predicate for a loaded VocabItem."""
    return (
        w.language == "de"
        and w.pos == PartOfSpeech.NOUN
        and w.gender_source == "oracle"
        and w.gender in GENDER_ARTICLES
    )


def gender_eligible_clause() -> tuple:
    """The same predicate as SQLAlchemy conditions over VocabItem columns, to
    splat into `.where(*gender_eligible_clause())`."""
    return (
        VocabItem.language == "de",
        VocabItem.gender_source == "oracle",
        VocabItem.pos == PartOfSpeech.NOUN,
        VocabItem.gender.in_(list(GENDER_ARTICLES)),
    )
