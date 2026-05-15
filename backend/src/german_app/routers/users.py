from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from german_app.dependencies import CurrentUser, DBSession, LocaleDep
from german_app.i18n import SUPPORTED_LANGUAGES, t
from german_app.models import User
from german_app.schemas.user import UserOut, UserUpdate


class LanguageInfoOut(BaseModel):
    label: str
    speech_locale: str

router = APIRouter(prefix="/me", tags=["users"])


def _to_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        level=user.level,
        native_language=user.native_language,
        target_language=user.target_language,
        learning_context=user.learning_context,
    )


@router.get("", response_model=UserOut)
async def get_me(user: CurrentUser) -> UserOut:
    return _to_out(user)


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
    return _to_out(user)


@router.get("/languages", response_model=dict[str, LanguageInfoOut])
async def list_languages() -> dict[str, dict]:
    return SUPPORTED_LANGUAGES
