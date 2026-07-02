"""Cookie-JWT authentication for the streaming WebSocket.

The browser sends the httponly session cookie automatically on the WS
upgrade, so we reuse the existing fastapi-users JWTStrategy — no ticket,
no token-in-query (which would leak to logs). Origin allowlist is defense
in depth on top of samesite=strict.
"""

from __future__ import annotations

from klara.auth.backend import auth_backend
from klara.auth.db import get_user_db
from klara.auth.manager import get_user_manager
from klara.config import Settings
from klara.db import get_session
from klara.models import User


def origin_allowed(websocket, settings: Settings) -> bool:
    origin = websocket.headers.get("origin")
    return bool(origin) and origin in settings.cors_origin_list


async def authenticate_ws(websocket, settings: Settings) -> User | None:
    """Validate the auth cookie and return the active user, or None.

    Acquires its own DB session via `klara.db.get_session()` rather than
    taking one as a param: the WS endpoint (T9) has no FastAPI dependency
    injection for a per-request session the way HTTP routes do, so this
    helper is self-contained and only needs (websocket, settings) — same
    shape as `origin_allowed`, easy to call from one place at connect time.
    """
    token = websocket.cookies.get(settings.auth_cookie_name)
    if not token:
        return None
    strategy = auth_backend.get_strategy()
    async for session in get_session():
        async for user_db in get_user_db(session):
            async for user_manager in get_user_manager(user_db, settings, session):
                user = await strategy.read_token(token, user_manager)
                return user if (user and user.is_active) else None
    return None
