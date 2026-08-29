"""Transporte Bearer + estrategia en base de datos para el app nativo.

Convive con el backend de cookie (backend.py) sin tocarlo: FastAPIUsers recibe
los dos y `current_active_user` acepta cualquiera. Spec android §2.1.
"""

from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi_users.authentication import AuthenticationBackend, BearerTransport
from fastapi_users.authentication.strategy.db import AccessTokenDatabase, DatabaseStrategy
from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyAccessTokenDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from klara.auth.db import AuthSessionDep
from klara.config import get_settings
from klara.models import AccessToken, User

BearerStrategy = DatabaseStrategy[User, UUID, AccessToken]


async def get_access_token_db(
    session: AuthSessionDep,
) -> AsyncGenerator[SQLAlchemyAccessTokenDatabase[AccessToken], None]:
    yield SQLAlchemyAccessTokenDatabase(session, AccessToken)


def make_database_strategy(session: AsyncSession) -> BearerStrategy:
    """Sin inyección de dependencias: el WebSocket (ws_auth.py) trae su sesión."""
    return DatabaseStrategy(
        SQLAlchemyAccessTokenDatabase(session, AccessToken),
        lifetime_seconds=get_settings().auth_bearer_max_age,
    )


def get_database_strategy(
    access_token_db: Annotated[AccessTokenDatabase[AccessToken], Depends(get_access_token_db)],
) -> BearerStrategy:
    return DatabaseStrategy(access_token_db, lifetime_seconds=get_settings().auth_bearer_max_age)


StrategyDep = Annotated[BearerStrategy, Depends(get_database_strategy)]

bearer_transport = BearerTransport(tokenUrl="api/v1/auth/bearer/login")

bearer_backend = AuthenticationBackend(
    name="bearer-db",
    transport=bearer_transport,
    get_strategy=get_database_strategy,
)
