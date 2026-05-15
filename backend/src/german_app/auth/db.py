from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from german_app.db import get_session
from german_app.models import OAuthAccount, User


async def get_auth_session() -> AsyncGenerator[AsyncSession, None]:
    """Shared session for auth deps (user_db + user_manager use the same one)."""
    async for s in get_session():
        yield s


AuthSessionDep = Annotated[AsyncSession, Depends(get_auth_session)]


async def get_user_db(
    session: AuthSessionDep,
) -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    yield SQLAlchemyUserDatabase(session, User, OAuthAccount)


UserDbDep = Annotated[SQLAlchemyUserDatabase, Depends(get_user_db)]
