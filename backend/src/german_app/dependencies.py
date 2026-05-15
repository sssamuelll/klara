from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from german_app.auth.users import current_active_user
from german_app.config import Settings, get_settings
from german_app.db import get_session
from german_app.i18n.messages import DEFAULT_LOCALE
from german_app.llm.base import LLMClient
from german_app.llm.litellm_impl import LiteLLMClient
from german_app.models import User

SettingsDep = Annotated[Settings, Depends(get_settings)]


__all__ = ["ChatLLM", "CurrentUser", "DBSession", "LocaleDep", "SettingsDep", "StoryLLM"]


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
