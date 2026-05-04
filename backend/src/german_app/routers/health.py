from fastapi import APIRouter
from sqlalchemy import text

from german_app.dependencies import DBSession

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db")
async def health_db(db: DBSession) -> dict[str, str]:
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "component": "database"}
