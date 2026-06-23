"""Gender-axis API contracts (der/die/das), shared by the in-story grading path
(routers/stories.py) and the standalone gender review path (routers/gender.py).
Moved here from schemas/finish.py so the gender router's dependency cone stays
within the gender subsystem."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class GenderAttemptIn(BaseModel):
    vocab_item_id: UUID
    picked_article: Literal["der", "die", "das"]


class GenderRuleOut(BaseModel):
    suffix: str
    suffix_class: Literal["hard", "tendency"]
    rule_gender: Literal["der", "die", "das"]
    is_exception: bool


class GenderAttemptOut(BaseModel):
    was_correct: bool
    correct_gender: str
    rule: GenderRuleOut | None = None  # showable suffix rule (Case A/C); None otherwise


class GenderReviewItem(BaseModel):
    vocab_item_id: UUID
    lemma: str
    en: str | None = None  # native-language gloss for context; NOT the answer
