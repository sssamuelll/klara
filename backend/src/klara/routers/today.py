"""GET /today: el lobby en una sola llamada (spec 2026-09-30 §2)."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from klara.dependencies import CurrentUser, DBSession
from klara.schemas.today import TodayOut
from klara.services.today import build_today

router = APIRouter(prefix="/today", tags=["today"])

MAX_PAST = timedelta(hours=48)
MAX_FUTURE = timedelta(minutes=1)


@router.get("", response_model=TodayOut)
async def get_today(
    db: DBSession, user: CurrentUser, since: Annotated[datetime, Query()]
) -> TodayOut:
    """`since` es la medianoche local del dispositivo; «hoy» es el día del usuario."""
    now = datetime.now(UTC)
    if since.tzinfo is None or since > now + MAX_FUTURE or since < now - MAX_PAST:
        raise HTTPException(status_code=422, detail="today.since_out_of_range")
    return await build_today(db, user, since=since, now=now)
