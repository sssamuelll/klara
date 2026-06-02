"""Schemas for GET /api/v1/practice/queue.

The payload is shaped to match the frontend `PracticeQueue` / `PracticeItem`
TS contract 1:1, so the frontend swap (mock → fetch) is a one-liner. The
camelCase field names the TS expects (`focusText`, `focusTx`,
`targetLanguage`, `sourceTitle`) are emitted via `serialization_alias`, while
Python code constructs these models with snake/clean attribute names.

Scope (this PR): the queue is STRUGGLED-ONLY. `variants` is always `[]`
(variety-by-level is deferred to a later PR, mirroring the mock). `review`
(SRS-due) items are NOT produced here — see `services/practice_queue.py` for
the deferral notes.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# `reason` mirrors the TS `PracticeReason` union. This PR only ever emits
# "struggled"; "review" exists in the contract so the frontend type stays
# stable when SRS items land in a later PR.
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


class PracticeQueueOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[PracticeItemOut]
    target_language: str = Field(serialization_alias="targetLanguage")
    source_title: str = Field(serialization_alias="sourceTitle")
