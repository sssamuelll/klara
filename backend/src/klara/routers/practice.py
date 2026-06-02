"""GET /api/v1/practice/queue — today's pronunciation practice set.

Scope (this PR): STRUGGLED-ONLY. Returns sentences the learner recently
mispronounced, with the worst token surfaced as the focus word. `variants` is
always empty and `review` (SRS-due) items are deferred — see
`services/practice_queue.py` for the full deferral notes.

Auth-gated like the other routers. The queue is built against the user's own
attempts and their configured target language.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from klara.dependencies import CurrentUser, DBSession
from klara.schemas.practice import PracticeQueueOut
from klara.services.practice_queue import DEFAULT_QUEUE_LIMIT, build_struggled_queue

router = APIRouter(prefix="/practice", tags=["practice"])


@router.get("/queue", response_model=PracticeQueueOut, response_model_by_alias=True)
async def practice_queue(
    db: DBSession,
    user: CurrentUser,
    limit: int = Query(DEFAULT_QUEUE_LIMIT, ge=1, le=50),
) -> PracticeQueueOut:
    return await build_struggled_queue(
        db,
        user_id=user.id,
        target_language=user.target_language,
        limit=limit,
    )
