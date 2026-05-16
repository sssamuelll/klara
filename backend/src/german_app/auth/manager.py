from typing import TYPE_CHECKING, Annotated, Any
from uuid import UUID

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi_users import BaseUserManager, UUIDIDMixin, exceptions, models, schemas
from fastapi_users.password import PasswordHelper
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from german_app.auth.db import AuthSessionDep, UserDbDep
from german_app.auth.email import EmailService
from german_app.auth.invitations import InvitationService, require_active
from german_app.config import Settings, get_settings
from german_app.i18n.messages import DEFAULT_LOCALE, SUPPORTED, t
from german_app.models import User
from german_app.models.enums import CEFRLevel

if TYPE_CHECKING:
    from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

log = structlog.get_logger(__name__)

_password_helper = PasswordHelper(PasswordHash((Argon2Hasher(),)))


def _locale_from_request(request: Request | None) -> str:
    if request is None:
        return DEFAULT_LOCALE
    locale = getattr(request.state, "locale", DEFAULT_LOCALE)
    return locale if locale in SUPPORTED else DEFAULT_LOCALE


def _allowlist_blocked(settings: Settings, email: str) -> bool:
    allowed = settings.allowed_signup_email_set
    if not allowed:
        return False
    return email.strip().lower() not in allowed


def _allowlist_http_exception(locale: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=t("auth.allowlist_blocked", locale),
    )


class UserManager(UUIDIDMixin, BaseUserManager[User, UUID]):
    password_helper = _password_helper

    def __init__(
        self,
        user_db: "SQLAlchemyUserDatabase[User, UUID]",
        settings: Settings,
        session: AsyncSession,
        email_service: EmailService,
    ) -> None:
        super().__init__(user_db)
        self.settings = settings
        self.session = session
        self.email_service = email_service
        self.reset_password_token_secret = settings.auth_jwt_secret
        self.verification_token_secret = settings.auth_jwt_secret

    # --- hooks ---------------------------------------------------------------

    async def on_after_register(self, user: User, request: Request | None = None) -> None:
        log.info(
            "auth.user_registered",
            user_id=str(user.id),
            email=user.email,
            adopted=bool(getattr(request, "state", None) and getattr(request.state, "adopted_legacy", False)),
        )
        if user.email and not user.is_verified:
            try:
                await self.request_verify(user, request)
            except exceptions.UserInactive:
                pass
            except exceptions.UserAlreadyVerified:
                pass

    async def on_after_forgot_password(
        self, user: User, token: str, request: Request | None = None
    ) -> None:
        log.info("auth.forgot_password", user_id=str(user.id))
        await self.email_service.send_reset(user, token)

    async def on_after_request_verify(
        self, user: User, token: str, request: Request | None = None
    ) -> None:
        log.info("auth.request_verify", user_id=str(user.id))
        await self.email_service.send_verify(user, token)

    # --- overrides -----------------------------------------------------------

    async def create(
        self,
        user_create: schemas.UC,
        safe: bool = False,
        request: Request | None = None,
    ) -> User:
        await self.validate_password(user_create.password, user_create)
        email = user_create.email.strip().lower()
        locale = _locale_from_request(request)

        # Allowlist stays as defense-in-depth if the admin configured one;
        # otherwise the invite token is the only gate.
        if _allowlist_blocked(self.settings, email):
            raise _allowlist_http_exception(locale)

        existing_user = await self.user_db.get_by_email(email)
        if existing_user is not None:
            raise exceptions.UserAlreadyExists()

        # Bootstrap exception: the INITIAL_OWNER_EMAIL adopts the legacy row
        # without an invite (there's no admin yet to issue one).
        adopted = await self._adopt_legacy_if_owner(email, user_create, request)
        if adopted is not None:
            await self.on_after_register(adopted, request)
            return adopted

        invite_token = getattr(user_create, "invite_token", None)
        if not invite_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=t("auth.invite_required", locale),
            )
        invites = InvitationService(self.session)
        invite = require_active(await invites.get_by_token(invite_token), locale)
        if invite.email and invite.email != email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=t("auth.invite_email_mismatch", locale),
            )

        user_dict = (
            user_create.create_update_dict()
            if safe
            else user_create.create_update_dict_superuser()
        )
        user_dict["email"] = email
        password = user_dict.pop("password")
        user_dict["hashed_password"] = self.password_helper.hash(password)
        user_dict.pop("invite_token", None)
        user_dict = _apply_profile_defaults(user_dict, self.settings)

        created_user = await self.user_db.create(user_dict)
        await invites.mark_used(invite.id, created_user.id)
        await self.on_after_register(created_user, request)
        return created_user

    async def oauth_callback(  # type: ignore[override]
        self,
        oauth_name: str,
        access_token: str,
        account_id: str,
        account_email: str,
        expires_at: int | None = None,
        refresh_token: str | None = None,
        request: Request | None = None,
        *,
        associate_by_email: bool = False,
        is_verified_by_default: bool = False,
    ) -> User:
        account_email = account_email.strip().lower()
        locale = _locale_from_request(request)

        # If we already know this oauth account, let the parent handle the
        # update path — no allowlist re-check on every login.
        try:
            await self.get_by_oauth_account(oauth_name, account_id)
        except exceptions.UserNotExists:
            if _allowlist_blocked(self.settings, account_email):
                raise _allowlist_http_exception(locale) from None
            adopted = await self._adopt_legacy_if_owner_oauth(
                account_email,
                oauth_name,
                access_token,
                account_id,
                expires_at,
                refresh_token,
                request,
            )
            if adopted is not None:
                return adopted
            # Brand-new OAuth user, not the bootstrap owner -> only allowed if
            # the email already exists in the users table (i.e. they previously
            # signed up via invite and are now linking Google). Otherwise we
            # silently treat OAuth as login-only, never invite-bypassing signup.
            existing = await self.user_db.get_by_email(account_email)
            if existing is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=t("auth.invite_required", locale),
                ) from None

        return await super().oauth_callback(
            oauth_name,
            access_token,
            account_id,
            account_email,
            expires_at,
            refresh_token,
            request,
            associate_by_email=associate_by_email,
            is_verified_by_default=is_verified_by_default,
        )

    # --- adoption helpers ----------------------------------------------------

    async def _legacy_owner_candidate(self, incoming_email: str) -> User | None:
        owner_email = self.settings.initial_owner_email_normalized
        if owner_email is None or owner_email != incoming_email:
            return None
        # FOR UPDATE locks the candidate row for the duration of this
        # transaction so two concurrent owner signups can't both adopt the
        # same legacy row. The second waiter sees the row already claimed
        # (email set) and falls through to UserAlreadyExists upstream.
        stmt = select(User).where(User.email.is_(None)).with_for_update()
        candidates = (await self.session.execute(stmt)).scalars().all()
        if len(candidates) != 1:
            if len(candidates) > 1:
                log.warning("auth.legacy_owner_ambiguous", count=len(candidates))
            return None
        return candidates[0]

    async def _adopt_legacy_if_owner(
        self,
        email: str,
        user_create: schemas.UC,
        request: Request | None,
    ) -> User | None:
        legacy = await self._legacy_owner_candidate(email)
        if legacy is None:
            return None

        legacy.email = email
        legacy.hashed_password = self.password_helper.hash(user_create.password)
        legacy.is_active = True
        legacy.is_verified = False
        legacy.is_superuser = True  # the owner is the admin

        display_name = getattr(user_create, "display_name", None)
        if display_name:
            legacy.display_name = display_name
        level = getattr(user_create, "level", None)
        if level is not None:
            legacy.level = level
        native_language = getattr(user_create, "native_language", None)
        if native_language:
            legacy.native_language = native_language
        target_language = getattr(user_create, "target_language", None)
        if target_language:
            legacy.target_language = target_language
        if "learning_context" in user_create.model_fields_set:
            legacy.learning_context = user_create.learning_context

        await self.session.commit()
        await self.session.refresh(legacy)
        if request is not None:
            request.state.adopted_legacy = True
        log.info("auth.legacy_owner_adopted", user_id=str(legacy.id), email=email)
        return legacy

    async def _adopt_legacy_if_owner_oauth(
        self,
        account_email: str,
        oauth_name: str,
        access_token: str,
        account_id: str,
        expires_at: int | None,
        refresh_token: str | None,
        request: Request | None,
    ) -> User | None:
        legacy = await self._legacy_owner_candidate(account_email)
        if legacy is None:
            return None

        legacy.email = account_email
        legacy.is_active = True
        legacy.is_verified = True
        legacy.is_superuser = True  # the owner is the admin

        await self.session.commit()
        await self.session.refresh(legacy)

        oauth_account_dict: dict[str, Any] = {
            "oauth_name": oauth_name,
            "access_token": access_token,
            "account_id": account_id,
            "account_email": account_email,
            "expires_at": expires_at,
            "refresh_token": refresh_token,
        }
        legacy = await self.user_db.add_oauth_account(legacy, oauth_account_dict)
        if request is not None:
            request.state.adopted_legacy = True
        log.info(
            "auth.legacy_owner_adopted_oauth",
            user_id=str(legacy.id),
            oauth_name=oauth_name,
        )
        return legacy


def _apply_profile_defaults(user_dict: dict[str, Any], settings: Settings) -> dict[str, Any]:
    user_dict.setdefault("display_name", settings.default_user_display_name)
    if user_dict.get("level") is None:
        user_dict["level"] = CEFRLevel(settings.default_user_level)
    user_dict.setdefault("native_language", settings.default_user_native_language)
    user_dict.setdefault("target_language", settings.default_user_target_language)
    user_dict.setdefault("learning_context", settings.default_user_learning_context)
    return user_dict


_ = models  # keep name available for fastapi-users' generic protocols


SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_user_manager(
    user_db: UserDbDep,
    settings: SettingsDep,
    session: AuthSessionDep,
):
    email_service = EmailService(settings)
    yield UserManager(user_db, settings, session, email_service)
