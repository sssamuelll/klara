"""Shared gender grading — the single source of truth for grading a der/die/das
pick against the oracle and recording the diadic evidence. Framework-free: it
returns GenderAttemptOut | None (None = not oracle-gradable) and never raises an
HTTP error; routers map None to a localized 404. Called by both the in-story
finish path (routers/stories.py) and the standalone review path
(routers/gender.py)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from klara.curriculum.gender_rules import detect_gender_rule, reconcile_rule
from klara.models import GenderAttempt, VocabItem
from klara.schemas.gender import GenderAttemptOut, GenderRuleOut


async def grade_gender_attempt(
    db: AsyncSession, *, user_id: UUID, vocab_item_id: UUID, picked_article: str
) -> GenderAttemptOut | None:
    """Grade the pick against the oracle gender and record the evidence. Returns
    None when the vocab is not oracle-gradable (missing / gender_source != 'oracle'
    / no gender) — an LLM/user guess is never certified as evidence (the curriculum
    invariant). The returned value is a function of inputs + oracle (no read-back of
    the committed row); single commit, no refresh — matching the prior handler."""
    vocab = await db.get(VocabItem, vocab_item_id)
    if vocab is None or vocab.gender_source != "oracle" or not vocab.gender:
        return None
    was_correct = picked_article == vocab.gender
    rule = detect_gender_rule(vocab.lemma)
    detail = reconcile_rule(rule, vocab.gender, vocab.lemma) if rule is not None else None
    rule_out = None
    if detail is not None and (detail["agreement"] or detail["is_exception"]):
        rule_out = GenderRuleOut(
            suffix=detail["suffix"],
            suffix_class=detail["suffix_class"],
            rule_gender=detail["rule_gender"],
            is_exception=detail["is_exception"],
        )
    db.add(
        GenderAttempt(
            user_id=user_id,
            vocab_item_id=vocab.id,
            picked_article=picked_article,
            was_correct=was_correct,
            detail=detail,
        )
    )
    await db.commit()
    return GenderAttemptOut(was_correct=was_correct, correct_gender=vocab.gender, rule=rule_out)
