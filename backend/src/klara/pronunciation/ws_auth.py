"""Cookie-JWT authentication for the streaming WebSocket.

The browser sends the httponly session cookie automatically on the WS
upgrade, so we reuse the existing fastapi-users JWTStrategy — no ticket,
no token-in-query (which would leak to logs). Origin allowlist is defense
in depth on top of samesite=strict.
"""

from __future__ import annotations

import contextlib

from starlette.websockets import WebSocket

from klara.auth.backend import auth_backend
from klara.auth.db import get_user_db
from klara.auth.manager import get_user_manager
from klara.config import Settings
from klara.db import get_session
from klara.models import User


def origin_allowed(websocket: WebSocket, settings: Settings) -> bool:
    origin = websocket.headers.get("origin")
    return bool(origin) and origin in settings.cors_origin_list


async def authenticate_ws(websocket: WebSocket, settings: Settings) -> User | None:
    """Validate the auth cookie and return the active user, or None.

    Acquires its own DB session via `klara.db.get_session()` rather than
    taking one as a param: the WS endpoint (T9) has no FastAPI dependency
    injection for a per-request session the way HTTP routes do, so this
    helper is self-contained and only needs (websocket, settings) — same
    shape as `origin_allowed`, easy to call from one place at connect time.

    Every generator in the get_session -> get_user_db -> get_user_manager
    chain is wrapped in `contextlib.aclosing()` so its `finally`/`__aexit__`
    runs synchronously before we return, instead of being deferred to the
    asyncgen-finalizer hook on a later loop tick.
    """
    token = websocket.cookies.get(settings.auth_cookie_name)
    if not token:
        return None
    strategy = auth_backend.get_strategy()
    async with contextlib.aclosing(get_session()) as sessions:
        async for session in sessions:
            async with contextlib.aclosing(get_user_db(session)) as user_dbs:
                async for user_db in user_dbs:
                    async with contextlib.aclosing(
                        get_user_manager(user_db, settings, session)
                    ) as managers:
                        async for user_manager in managers:
                            user = await strategy.read_token(token, user_manager)
                            return user if (user and user.is_active) else None
    return None
