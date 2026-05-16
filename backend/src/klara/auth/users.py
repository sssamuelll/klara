from uuid import UUID

from fastapi_users import FastAPIUsers

from klara.auth.backend import auth_backend
from klara.auth.manager import get_user_manager
from klara.models import User

fastapi_users: FastAPIUsers[User, UUID] = FastAPIUsers[User, UUID](
    get_user_manager,
    [auth_backend],
)

# Verified-gating is intentionally off for the MVP — verify-email is informational,
# not blocking. Flip to active=True, verified=True once the email pipeline is
# fully exercised in prod.
current_active_user = fastapi_users.current_user(active=True)
current_admin_user = fastapi_users.current_user(active=True, superuser=True)

__all__ = [
    "auth_backend",
    "current_active_user",
    "current_admin_user",
    "fastapi_users",
    "get_user_manager",
]
