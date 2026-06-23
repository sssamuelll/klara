from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from klara.curriculum.competence import weak_gender_nouns
from klara.dependencies import CurrentUser, DBSession, LocaleDep
from klara.i18n import t
from klara.models import VocabItem
from klara.schemas.gender import GenderAttemptIn, GenderAttemptOut, GenderReviewItem
from klara.services.gender_grading import grade_gender_attempt

router = APIRouter(prefix="/gender", tags=["gender"])


async def _load_words_ordered(db: DBSession, ids: list[UUID]) -> list[VocabItem]:
    """Load VocabItems for `ids`, preserving the input order."""
    rows = (await db.execute(select(VocabItem).where(VocabItem.id.in_(ids)))).scalars().all()
    by_id = {w.id: w for w in rows}
    return [by_id[i] for i in ids if i in by_id]


@router.get("/review", response_model=list[GenderReviewItem])
async def gender_review(
    db: DBSession, user: CurrentUser, limit: int = Query(20, ge=1, le=100)
) -> list[GenderReviewItem]:
    """The user's weak der/die/das nouns, priority-ordered. The answer is never
    in the payload — revealed only on grading. Empty when the user has no weak
    nouns (caught up, or never started)."""
    ids = await weak_gender_nouns(db, user_id=user.id, limit=limit)
    if not ids:
        return []
    words = await _load_words_ordered(db, ids)
    return [
        GenderReviewItem(
            vocab_item_id=w.id,
            lemma=w.lemma,
            en=(w.translations or {}).get(user.native_language),
        )
        for w in words
    ]


@router.post("/attempts", response_model=GenderAttemptOut, status_code=status.HTTP_201_CREATED)
async def grade(
    payload: GenderAttemptIn, db: DBSession, user: CurrentUser, locale: LocaleDep
) -> GenderAttemptOut:
    """Grade a standalone der/die/das pick (no story scope). Oracle-gated: 404 if
    the noun is not oracle-gradable. The attempt is recorded for the caller."""
    out = await grade_gender_attempt(
        db,
        user_id=user.id,
        vocab_item_id=payload.vocab_item_id,
        picked_article=payload.picked_article,
    )
    if out is None:
        raise HTTPException(status_code=404, detail=t("errors.vocab_not_found", locale))
    return out
