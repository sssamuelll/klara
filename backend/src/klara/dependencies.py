from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from klara.auth.manager import UserManager, get_user_manager
from klara.auth.users import current_active_user
from klara.config import Settings, get_settings
from klara.db import get_session
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
    "UserManagerDep",
]


def get_locale(request: Request) -> str:
    return getattr(request.state, "locale", DEFAULT_LOCALE)


LocaleDep = Annotated[str, Depends(get_locale)]


async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async for s in get_session():
        yield s


DBSession = Annotated[AsyncSession, Depends(db_session)]


def get_story_llm(settings: SettingsDep) -> LLMClient:
    return LiteLLMClient(settings, default_model=settings.llm_story_model)


def get_chat_llm(settings: SettingsDep) -> LLMClient:
    return LiteLLMClient(settings, default_model=settings.llm_chat_model)


StoryLLM = Annotated[LLMClient, Depends(get_story_llm)]
ChatLLM = Annotated[LLMClient, Depends(get_chat_llm)]


CurrentUser = Annotated[User, Depends(current_active_user)]
UserManagerDep = Annotated[UserManager, Depends(get_user_manager)]
