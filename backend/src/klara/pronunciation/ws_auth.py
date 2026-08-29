"""Autenticación del WebSocket de streaming: cookie (navegador) o token Bearer
del app nativo, leído del primer frame (spec android §2.3).

El navegador manda la cookie httponly sola en el upgrade; el app no tiene
cookie y manda el token dentro del handshake JSON — nunca en la URL (se filtra
a logs) ni en headers (el WebSocket del navegador no permite fijarlos). La
allowlist de Origin es defensa en profundidad encima de las dos.
"""

from __future__ import annotations

import contextlib

from starlette.websockets import WebSocket

from klara.auth.backend import auth_backend
from klara.auth.bearer import make_database_strategy
from klara.auth.db import get_user_db
from klara.auth.manager import get_user_manager
from klara.config import Settings
from klara.db import get_session
from klara.models import User


def origin_allowed(websocket: WebSocket, settings: Settings) -> bool:
    origin = websocket.headers.get("origin")
    return bool(origin) and origin in settings.cors_origin_list


async def authenticate_ws(
    websocket: WebSocket, settings: Settings, token: str | None = None
) -> User | None:
    """Cookie primero; si no hay, el token Bearer del handshake. None si nada vale.

    Sesión propia vía get_session() (el endpoint WS no tiene DI por petición);
    cada generador de la cadena get_session -> get_user_db -> get_user_manager
    va en contextlib.aclosing() para que su cierre corra antes de retornar.
    """
    cookie = websocket.cookies.get(settings.auth_cookie_name)
    if not cookie and not token:
        return None
    async with contextlib.aclosing(get_session()) as sessions:
        async for session in sessions:
            async with contextlib.aclosing(get_user_db(session)) as user_dbs:
                async for user_db in user_dbs:
                    async with contextlib.aclosing(
                        get_user_manager(user_db, settings, session)
                    ) as managers:
                        async for user_manager in managers:
                            if cookie:
                                user = await auth_backend.get_strategy().read_token(
                                    cookie, user_manager
                                )
                            else:
                                user = await make_database_strategy(session).read_token(
                                    token, user_manager
                                )
                            return user if (user and user.is_active) else None
    return None
