from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from german_app.config import Settings, get_settings
from german_app.db import get_session
from german_app.llm.base import LLMClient
from german_app.llm.litellm_impl import LiteLLMClient
from german_app.models import User
from german_app.models.enums import CEFRLevel

SettingsDep = Annotated[Settings, Depends(get_settings)]


__all__ = ["CurrentUser", "DBSession", "SettingsDep", "ChatLLM", "StoryLLM"]


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


async def current_user(db: DBSession, settings: SettingsDep) -> User:
    stmt = select(User).order_by(User.created_at.asc()).limit(1)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is not None:
        return user
    user = User(
        display_name=settings.default_user_display_name,
        level=CEFRLevel(settings.default_user_level),
        native_language=settings.default_user_native_language,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


CurrentUser = Annotated[User, Depends(current_user)]
