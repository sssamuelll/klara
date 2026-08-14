from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from klara.auth.db import get_auth_session
from klara.auth.manager import UserManager, get_user_manager
from klara.auth.users import current_active_user
from klara.config import Settings, get_settings
from klara.i18n.messages import DEFAULT_LOCALE
from klara.llm.base import LLMClient
from klara.llm.litellm_impl import LiteLLMClient
from klara.models import User

SettingsDep = Annotated[Settings, Depends(get_settings)]


__all__ = [
    "ChatLLM",
    "CurrentUser",
    "DBSession",
    "LocaleDep",
    "SettingsDep",
    "StoryLLM",
    "TallerUser",
    "UserManagerDep",
]


def get_locale(request: Request) -> str:
    return getattr(request.state, "locale", DEFAULT_LOCALE)


LocaleDep = Annotated[str, Depends(get_locale)]


async def db_session(session: Annotated[AsyncSession, Depends(get_auth_session)]) -> AsyncSession:
    # Reuse the same per-request session as the auth deps (get_auth_session):
    # CurrentUser and DBSession must be the SAME session, or a route that
    # mutates `user` fields and commits via `db` silently loses the write
    # (the auth session's context manager closes without committing).
    return session


DBSession = Annotated[AsyncSession, Depends(db_session)]


def get_story_llm(settings: SettingsDep) -> LLMClient:
    return LiteLLMClient(
        settings,
        default_model=settings.llm_story_model,
        default_extra_body=settings.llm_story_extra_body,
    )


def get_chat_llm(settings: SettingsDep) -> LLMClient:
    return LiteLLMClient(
        settings,
        default_model=settings.llm_chat_model,
        default_extra_body=settings.llm_chat_extra_body,
    )


StoryLLM = Annotated[LLMClient, Depends(get_story_llm)]
ChatLLM = Annotated[LLMClient, Depends(get_chat_llm)]


CurrentUser = Annotated[User, Depends(current_active_user)]
UserManagerDep = Annotated[UserManager, Depends(get_user_manager)]


def _require_taller_access(user: CurrentUser, settings: SettingsDep) -> User:
    """El guard de F0: fuera de `taller_user_ids` -> 403. Cerrado por defecto
    (el ajuste nace vacío) para que el dogfood no despliegue escritura sin
    cuota a cualquier cuenta autenticada."""
    if str(user.id) not in settings.taller_user_id_set:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not_in_taller_allowlist")
    return user


TallerUser = Annotated[User, Depends(_require_taller_access)]
