"""grade_gender_attempt (shared gender grading) + the consolidated gender schemas."""

import uuid


def test_gender_schemas_live_in_gender_module():
    from klara.schemas.gender import (
        GenderAttemptIn,
        GenderAttemptOut,
        GenderReviewItem,
        GenderRuleOut,
    )

    item = GenderReviewItem(vocab_item_id=uuid.uuid4(), lemma="Tisch", en="mesa")
    assert item.en == "mesa"
    assert GenderAttemptIn(vocab_item_id=uuid.uuid4(), picked_article="der").picked_article == "der"
    out = GenderAttemptOut(was_correct=True, correct_gender="der", rule=None)
    assert out.rule is None
    assert (
        GenderRuleOut(
            suffix="ung", suffix_class="hard", rule_gender="die", is_exception=False
        ).rule_gender
        == "die"
    )
