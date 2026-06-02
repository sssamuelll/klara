"""GET /api/v1/practice/queue — today's pronunciation practice set.

Returns a combined set: sentences the learner recently mispronounced
(reason "struggled", worst token surfaced as focus) plus SRS-due vocab lines
to say aloud (reason "review"). A word that is both struggled and due appears
once, as struggled. `variants` is always empty — see
`services/practice_queue.py` for the full algorithm and deferral notes.

Auth-gated like the other routers. The queue is built against the user's own
attempts/cards and their configured target + native languages.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from klara.dependencies import CurrentUser, DBSession
from klara.schemas.practice import PracticeQueueOut
from klara.services.practice_queue import DEFAULT_QUEUE_LIMIT, build_practice_queue

router = APIRouter(prefix="/practice", tags=["practice"])


@router.get("/queue", response_model=PracticeQueueOut, response_model_by_alias=True)
async def practice_queue(
    db: DBSession,
    user: CurrentUser,
    limit: int = Query(DEFAULT_QUEUE_LIMIT, ge=1, le=50),
) -> PracticeQueueOut:
    return await build_practice_queue(
        db,
        user_id=user.id,
        target_language=user.target_language,
        native_language=user.native_language,
        limit=limit,
    )
