from contextlib import asynccontextmanager
from uuid import uuid4

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from german_app.auth.backend import auth_backend
from german_app.auth.oauth_google import make_google_oauth_client
from german_app.auth.schemas import UserCreate, UserRead
from german_app.auth.users import fastapi_users
from german_app.config import get_settings
from german_app.db import dispose_engine, get_session, init_engine
from german_app.i18n.messages import DEFAULT_LOCALE, SUPPORTED
from german_app.logging_setup import configure_logging
from german_app.models import User
from german_app.models.enums import CEFRLevel
from german_app.routers import health, srs, stories, tts, users

log = structlog.get_logger(__name__)


async def _ensure_legacy_owner_row() -> None:
    """
    If INITIAL_OWNER_EMAIL is configured and no user owns content yet, plant a
    legacy row (email IS NULL, no password) so the owner's first sign-up can
    adopt it and inherit any imported data. Idempotent.
    """
    settings = get_settings()
    if not settings.initial_owner_email_normalized:
        return
    async for db in get_session():
        existing = (await db.execute(select(User).limit(1))).scalar_one_or_none()
        if existing is not None:
            return
        user = User(
            email=None,
            hashed_password=None,
            is_active=True,
            is_verified=False,
            is_superuser=False,
            display_name=settings.default_user_display_name,
            level=CEFRLevel(settings.default_user_level),
            native_language=settings.default_user_native_language,
            target_language=settings.default_user_target_language,
            learning_context=settings.default_user_learning_context,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        log.info("startup.legacy_owner_row_planted", user_id=str(user.id))
        return


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings)
    init_engine(settings)
    log.info("startup", env=settings.app_env)
    try:
        await _ensure_legacy_owner_row()
    except Exception as exc:
        log.warning("startup.legacy_owner_skip", error=str(exc))
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


def _negotiate_locale(header: str) -> str:
    for tag in header.split(","):
        code = tag.split(";")[0].strip().split("-")[0].lower()
        if code in SUPPORTED:
            return code
    return DEFAULT_LOCALE


class LocaleMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.locale = _negotiate_locale(request.headers.get("accept-language", ""))
        return await call_next(request)


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
    app.add_middleware(LocaleMiddleware)

    auth_prefix = "/api/v1/auth"
    app.include_router(
        fastapi_users.get_auth_router(auth_backend),
        prefix=f"{auth_prefix}/jwt",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_register_router(UserRead, UserCreate),
        prefix=auth_prefix,
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_verify_router(UserRead),
        prefix=auth_prefix,
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_reset_password_router(),
        prefix=auth_prefix,
        tags=["auth"],
    )

    google_client = make_google_oauth_client(settings)
    if google_client is not None:
        app.include_router(
            fastapi_users.get_oauth_router(
                google_client,
                auth_backend,
                settings.auth_jwt_secret,
                redirect_url=f"{settings.app_base_url}/auth/google/callback",
                associate_by_email=True,
                is_verified_by_default=True,
            ),
            prefix=f"{auth_prefix}/google",
            tags=["auth"],
        )

    app.include_router(health.router, prefix="/api/v1")
    app.include_router(users.router, prefix="/api/v1")
    app.include_router(stories.router, prefix="/api/v1")
    app.include_router(srs.router, prefix="/api/v1")
    app.include_router(tts.router, prefix="/api/v1")

    return app


app = create_app()
