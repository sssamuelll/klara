"""Invitation tokens — the only way new users can self-register.

Bootstrap exception: if INITIAL_OWNER_EMAIL is configured and a legacy row
(email IS NULL) exists, that one signup is allowed without an invite. After
that, every new account needs a valid token issued by an admin.
"""
from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from klara.i18n.messages import t
from klara.models import Invitation

DEFAULT_TTL_DAYS = 7
TOKEN_BYTES = 24  # 24 bytes -> 32-char urlsafe string


def generate_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def _now() -> datetime:
    return datetime.now(UTC)


def is_active(inv: Invitation) -> bool:
    if inv.used_at is not None or inv.revoked_at is not None:
        return False
    expires_at = inv.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at > _now()


def invitation_state(inv: Invitation) -> str:
    if inv.revoked_at is not None:
        return "revoked"
    if inv.used_at is not None:
        return "used"
    expires_at = inv.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= _now():
        return "expired"
    return "active"


class InvitationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        created_by_id: UUID,
        email: str | None = None,
        note: str | None = None,
        ttl_days: int = DEFAULT_TTL_DAYS,
    ) -> Invitation:
        inv = Invitation(
            token=generate_token(),
            email=email.strip().lower() if email else None,
            note=note.strip() if note else None,
            created_by=created_by_id,
            expires_at=_now() + timedelta(days=ttl_days),
        )
        self.session.add(inv)
        await self.session.commit()
        await self.session.refresh(inv)
        return inv

    async def list_all(self) -> list[Invitation]:
        stmt = select(Invitation).order_by(Invitation.created_at.desc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def get(self, invitation_id: UUID) -> Invitation | None:
        return await self.session.get(Invitation, invitation_id)

    async def get_by_token(self, token: str) -> Invitation | None:
        stmt = select(Invitation).where(Invitation.token == token)
        return (await self.session.execute(stmt)).scalars().first()

    async def revoke(self, invitation_id: UUID) -> Invitation | None:
        inv = await self.get(invitation_id)
        if inv is None:
            return None
        if inv.revoked_at is None and inv.used_at is None:
            inv.revoked_at = _now()
            await self.session.commit()
            await self.session.refresh(inv)
        return inv

    async def mark_used(self, invitation_id: UUID, used_by_id: UUID) -> None:
        inv = await self.get(invitation_id)
        if inv is None:
            return
        inv.used_at = _now()
        inv.used_by = used_by_id
        await self.session.commit()


def require_active(inv: Invitation | None, locale: str) -> Invitation:
    """Raises a localized HTTPException if the invite isn't redeemable."""
    if inv is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("auth.invite_invalid", locale),
        )
    state = invitation_state(inv)
    if state == "active":
        return inv
    key = {
        "used": "auth.invite_used",
        "expired": "auth.invite_expired",
        "revoked": "auth.invite_revoked",
    }[state]
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=t(key, locale))
