from contextlib import asynccontextmanager
from uuid import uuid4

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from german_app.config import get_settings
from german_app.db import dispose_engine, get_session, init_engine
from german_app.logging_setup import configure_logging
from german_app.models import User
from german_app.models.enums import CEFRLevel
from german_app.routers import health, srs, stories, tts, users

log = structlog.get_logger(__name__)


async def _ensure_default_user() -> None:
    settings = get_settings()
    async for db in get_session():
        existing = (await db.execute(select(User).limit(1))).scalar_one_or_none()
        if existing is None:
            user = User(
                display_name=settings.default_user_display_name,
                level=CEFRLevel(settings.default_user_level),
                native_language=settings.default_user_native_language,
                target_language=settings.default_user_target_language,
                learning_context=settings.default_user_learning_context,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            log.info("startup.default_user_created", user_id=str(user.id))
        return


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings)
    init_engine(settings)
    log.info("startup", env=settings.app_env)
    try:
        await _ensure_default_user()
    except Exception as exc:
        log.warning("startup.default_user_skip", error=str(exc))
    yield
    await dispose_engine()
    log.info("shutdown")


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id, path=request.url.path)
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="German Learning App",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIDMiddleware)

    app.include_router(health.router, prefix="/api/v1")
    app.include_router(users.router, prefix="/api/v1")
    app.include_router(stories.router, prefix="/api/v1")
    app.include_router(srs.router, prefix="/api/v1")
    app.include_router(tts.router, prefix="/api/v1")

    return app


app = create_app()
