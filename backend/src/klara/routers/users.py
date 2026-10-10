from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi_users import exceptions as fa_exceptions
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from klara.catalogo.cargar import get_catalogo
from klara.dependencies import ChatLLM, CurrentUser, DBSession, LocaleDep, UserManagerDep
from klara.i18n import SUPPORTED_LANGUAGES, t
from klara.models import LearnerProfile, OAuthAccount, User
from klara.schemas.learner_profile import LearnerProfileIn, LearnerProfileOut
from klara.schemas.user import SetPasswordIn, UserOut, UserUpdate
from klara.services.learner_synthesis import refresh_derived
from klara.services.sesion import idiomas_de_estudio

log = structlog.get_logger(__name__)


class LanguageInfoOut(BaseModel):
    label: str
    speech_locale: str


router = APIRouter(prefix="/me", tags=["users"])


async def _to_out(db: AsyncSession, user: User) -> UserOut:
    oauth_names = (
        (
            await db.execute(
                select(OAuthAccount.oauth_name).where(OAuthAccount.user_id == user.id).distinct()
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
        study_languages=idiomas_de_estudio(user, get_catalogo()),
    )


@router.get("", response_model=UserOut)
async def get_me(db: DBSession, user: CurrentUser) -> UserOut:
    return await _to_out(db, user)


@router.patch("", response_model=UserOut)
async def update_me(
    payload: UserUpdate, db: DBSession, user: CurrentUser, locale: LocaleDep
) -> UserOut:
    data = payload.model_dump(exclude_unset=True)

    # cross-check after merging with existing values — but only when this PATCH
    # actually touches a language. A display_name-only update must not be
    # rejected just because the *stored* pair is equal: a German-locale signup
    # seeds native="de" (browser lang) while target defaults to "de", and the
    # onboarding name step PATCHes before the languages step that would fix it.
    # Guarding pre-existing equality here traps the user before they can reach
    # that step. Only the incoming change is our business.
    if "native_language" in data or "target_language" in data:
        new_native = data.get("native_language", user.native_language)
        new_target = data.get("target_language", user.target_language)
        if new_native == new_target:
            raise HTTPException(
                status_code=422,
                detail=t("errors.languages_must_differ", locale),
            )
    # Todo lo que puede dar 422 va antes de la primera asignación: nada queda a medias.
    nuevos = data.get("study_languages")
    if nuevos is not None and any(i not in get_catalogo().mapas for i in nuevos):
        raise HTTPException(status_code=422, detail="study_languages.sin_mapa")

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
    if "study_languages" in data:
        user.study_languages = nuevos

    await db.commit()
    await db.refresh(user)
    return await _to_out(db, user)


@router.post("/onboarding/complete", response_model=UserOut)
async def complete_onboarding(db: DBSession, user: CurrentUser) -> UserOut:
    # CurrentUser and DBSession share one per-request session (see
    # klara.dependencies.db_session), so `user` is already persistent in `db`.
    if user.onboarding_completed_at is None:
        user.onboarding_completed_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(user)
        log.info("auth.onboarding_completed", user_id=str(user.id))
    return await _to_out(db, user)


@router.get("/learning-profile", response_model=LearnerProfileOut)
async def get_learning_profile(db: DBSession, user: CurrentUser) -> LearnerProfileOut:
    row = await db.get(LearnerProfile, user.id)
    if row is None:
        # «No existe» no se disfraza de «existe vacío»: los defaults viven en la
        # generación, no en el read path.
        raise HTTPException(status_code=404, detail="learning profile not found")
    return LearnerProfileOut.from_row(row)


@router.put("/learning-profile", response_model=LearnerProfileOut)
async def put_learning_profile(
    payload: LearnerProfileIn,
    db: DBSession,
    user: CurrentUser,
    llm: ChatLLM,
    background: BackgroundTasks,
    locale: LocaleDep,
    expected_version: int | None = Query(None),
) -> LearnerProfileOut:
    row = await db.get(LearnerProfile, user.id)
    if row is None:
        # expected_version es opcional solo en la creación.
        row = LearnerProfile(
            user_id=user.id,
            answers=payload.answers,
            timings=payload.timings,
            version=1,
        )
        db.add(row)
    else:
        if expected_version is None or expected_version != row.version:
            raise HTTPException(status_code=409, detail="version conflict")
        # PUT es reemplazo completo: lo que no viene, desaparece.
        row.answers = payload.answers
        row.timings = payload.timings
        row.version += 1
    await db.commit()
    await db.refresh(row)

    # Los derivados se regeneran aparte: guardar nunca falla por culpa de la
    # síntesis. Se estampa la versión que se sintetizó, no la vigente al
    # terminar — dos guardados seguidos no pueden declarar fresca a una vieja.
    background.add_task(
        refresh_derived,
        user_id=user.id,
        version=row.version,
        answers=row.answers,
        llm=llm,
        locale=locale,
    )
    return LearnerProfileOut.from_row(row)


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
    user.hashed_password = user_manager.password_helper.hash(payload.password)
    await db.commit()
    await db.refresh(user)
    log.info("auth.password_set", user_id=str(user.id))
    return await _to_out(db, user)


@router.get("/languages", response_model=dict[str, LanguageInfoOut])
async def list_languages() -> dict[str, dict]:
    return SUPPORTED_LANGUAGES
