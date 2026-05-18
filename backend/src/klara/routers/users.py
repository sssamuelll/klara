from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, HTTPException
from fastapi_users import exceptions as fa_exceptions
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from klara.dependencies import CurrentUser, DBSession, LocaleDep, UserManagerDep
from klara.i18n import SUPPORTED_LANGUAGES, t
from klara.models import OAuthAccount, User
from klara.schemas.user import SetPasswordIn, UserOut, UserUpdate

log = structlog.get_logger(__name__)


class LanguageInfoOut(BaseModel):
    label: str
    speech_locale: str

router = APIRouter(prefix="/me", tags=["users"])


async def _to_out(db: AsyncSession, user: User) -> UserOut:
    oauth_names = (
        (
            await db.execute(
                select(OAuthAccount.oauth_name)
                .where(OAuthAccount.user_id == user.id)
                .distinct()
            )
        )
        .scalars()
        .all()
    )
    methods: list[str] = []
    if user.hashed_password is not None:
        methods.append("password")
    methods.extend(name for name in oauth_names if name not in methods)
    methods.sort()  # estable alfabético

    return UserOut(
        id=user.id,
        email=user.email,
        is_superuser=user.is_superuser,
        display_name=user.display_name,
        level=user.level,
        native_language=user.native_language,
        target_language=user.target_language,
        learning_context=user.learning_context,
        auth_methods=methods,
        needs_onboarding=user.onboarding_completed_at is None,
    )


@router.get("", response_model=UserOut)
async def get_me(db: DBSession, user: CurrentUser) -> UserOut:
    return await _to_out(db, user)


async def _reload_in_db(db: AsyncSession, user: User) -> User:
    """CurrentUser comes from fastapi-users' auth session (a different session
    than our DBSession). Re-fetch the row in the router's session so any
    mutations + commit + refresh operate on a persistent instance."""
    return (
        await db.execute(select(User).where(User.id == user.id))
    ).scalar_one()


@router.patch("", response_model=UserOut)
async def update_me(
    payload: UserUpdate, db: DBSession, user: CurrentUser, locale: LocaleDep
) -> UserOut:
    data = payload.model_dump(exclude_unset=True)

    # cross-check after merging with existing values
    new_native = data.get("native_language", user.native_language)
    new_target = data.get("target_language", user.target_language)
    if new_native == new_target:
        raise HTTPException(
            status_code=422,
            detail=t("errors.languages_must_differ", locale),
        )

    user = await _reload_in_db(db, user)

    if data.get("display_name"):
        user.display_name = data["display_name"]
    if data.get("level") is not None:
        user.level = data["level"]
    if data.get("native_language"):
        user.native_language = data["native_language"]
    if data.get("target_language"):
        user.target_language = data["target_language"]
    if "learning_context" in data:
        ctx = data["learning_context"]
        user.learning_context = ctx.strip() if isinstance(ctx, str) and ctx.strip() else None

    await db.commit()
    await db.refresh(user)
    return await _to_out(db, user)


@router.post("/onboarding/complete", response_model=UserOut)
async def complete_onboarding(db: DBSession, user: CurrentUser) -> UserOut:
    user = await _reload_in_db(db, user)
    if user.onboarding_completed_at is None:
        user.onboarding_completed_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(user)
        log.info("auth.onboarding_completed", user_id=str(user.id))
    return await _to_out(db, user)


@router.post("/password", response_model=UserOut)
async def set_password(
    payload: SetPasswordIn,
    db: DBSession,
    user: CurrentUser,
    user_manager: UserManagerDep,
    locale: LocaleDep,
) -> UserOut:
    if user.hashed_password is not None:
        raise HTTPException(409, t("auth.password_already_set", locale))
    try:
        await user_manager.validate_password(payload.password, user)
    except fa_exceptions.InvalidPasswordException as e:
        raise HTTPException(422, t("auth.password_invalid", locale)) from e
    user = await _reload_in_db(db, user)
    user.hashed_password = user_manager.password_helper.hash(payload.password)
    await db.commit()
    await db.refresh(user)
    log.info("auth.password_set", user_id=str(user.id))
    return await _to_out(db, user)


@router.get("/languages", response_model=dict[str, LanguageInfoOut])
async def list_languages() -> dict[str, dict]:
    return SUPPORTED_LANGUAGES
