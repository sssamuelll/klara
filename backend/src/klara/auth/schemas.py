from uuid import UUID

from fastapi_users import schemas

from klara.models.enums import CEFRLevel


class UserRead(schemas.BaseUser[UUID]):
    display_name: str
    level: CEFRLevel
    native_language: str
    target_language: str
    learning_context: str | None = None


class UserCreate(schemas.BaseUserCreate):
    display_name: str | None = None
    level: CEFRLevel | None = None
    native_language: str | None = None
    target_language: str | None = None
    learning_context: str | None = None
    # Required for every signup except the bootstrap owner (the user matching
    # INITIAL_OWNER_EMAIL adopting the legacy row). Validated server-side.
    invite_token: str | None = None


class UserUpdate(schemas.BaseUserUpdate):
    display_name: str | None = None
    level: CEFRLevel | None = None
    native_language: str | None = None
    target_language: str | None = None
    learning_context: str | None = None
