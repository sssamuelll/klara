"""Schemas for GET /api/v1/practice/queue.

The payload is shaped to match the frontend `PracticeQueue` / `PracticeItem`
TS contract 1:1, so the frontend swap (mock → fetch) is a one-liner. The
camelCase field names the TS expects (`focusText`, `focusTx`,
`targetLanguage`, `sourceTitle`) are emitted via `serialization_alias`, while
Python code constructs these models with snake/clean attribute names.

The queue mixes "struggled" and "review" items. `variants` is always `[]`
(variety-by-level is deferred to a later PR, mirroring the mock) — see
`services/practice_queue.py` for the full algorithm and deferral notes.
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# `reason` mirrors the TS `PracticeReason` union: a line is either a recently
# mispronounced sentence ("struggled") or an SRS-due vocab line ("review").
PracticeReason = Literal["struggled", "review"]


class PracticeSentenceOut(BaseModel):
    """The origin line a Practice item carries (matches StorySentence's
    spoken/scored contract: `target` is said aloud, `native` is the gloss)."""

    target: str
    native: str


class PracticeItemOut(BaseModel):
    # populate_by_name lets us build the model with Python attribute names
    # (focus_text=...) while serialization emits the camelCase aliases the TS
    # contract expects (focusText). by_alias=True is set on the response.
    model_config = ConfigDict(populate_by_name=True)

    sentence: PracticeSentenceOut
    # Empty in this PR; populated by a later PR (variety-by-level). The TS type
    # already carries `variants`, so emitting [] keeps the swap a one-liner.
    variants: list[PracticeSentenceOut] = Field(default_factory=list)
    # Title of the story this line came from.
    source: str
    focus_text: str = Field(serialization_alias="focusText")
    focus_tx: str = Field(serialization_alias="focusTx")
    reason: PracticeReason
    # Provenance for attempt persistence FROM Practice (PR #3b). When BOTH are
    # set, the frontend POSTs a scored take of this line back to
    # /stories/{storyId}/pronunciation/attempts using `sentenceIndex` as the
    # index INTO that story's sentences — NOT the item's position in the Practice
    # queue. They are optional because a "review" item that fell back to the
    # vocab item's `example_target` has no origin story sentence to attribute
    # the attempt to (None → that item is not persisted).
    story_id: str | None = Field(default=None, serialization_alias="storyId")
    sentence_index: int | None = Field(default=None, serialization_alias="sentenceIndex")
    # Identidad de la UserCard SRS que respalda este item, cuando la hay. La cola
    # YA resuelve la carta (build_review_items) y el dedup struggled∩review matchea
    # el lemma — portarla aquí deja que el cierre del ciclo reprograme POR ID, sin
    # re-resolver por texto aguas abajo (que colapsa para formas flexionadas).
    card_id: UUID | None = Field(default=None, serialization_alias="cardId")


class PracticeQueueOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[PracticeItemOut]
    target_language: str = Field(serialization_alias="targetLanguage")
    source_title: str = Field(serialization_alias="sourceTitle")
