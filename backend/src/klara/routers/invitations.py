from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from klara.auth.db import AuthSessionDep
from klara.auth.invitations import InvitationService, invitation_state
from klara.auth.users import current_admin_user
from klara.config import Settings, get_settings
from klara.models import Invitation, User

router = APIRouter()

AdminUser = Annotated[User, Depends(current_admin_user)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


class InvitationCreateIn(BaseModel):
    email: EmailStr | None = None
    note: str | None = Field(default=None, max_length=255)
    ttl_days: int = Field(default=7, ge=1, le=90)


class InvitationOut(BaseModel):
    id: UUID
    token: str
    email: str | None
    note: str | None
    created_at: datetime
    expires_at: datetime
    used_at: datetime | None
    used_by: UUID | None
    revoked_at: datetime | None
    state: str
    share_url: str

    @classmethod
    def from_model(cls, inv: Invitation, frontend_base_url: str) -> "InvitationOut":
        return cls(
            id=inv.id,
            token=inv.token,
            email=inv.email,
            note=inv.note,
            created_at=inv.created_at,
            expires_at=inv.expires_at,
            used_at=inv.used_at,
            used_by=inv.used_by,
            revoked_at=inv.revoked_at,
            state=invitation_state(inv),
            share_url=f"{frontend_base_url.rstrip('/')}/signup?invite={inv.token}",
        )


class InvitationPublicOut(BaseModel):
    """Subset visible to anyone holding the token — used to prefill /signup."""

    email: str | None
    expires_at: datetime
    state: str


@router.post(
    "/admin/invitations",
    response_model=InvitationOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_invitation(
    payload: InvitationCreateIn,
    session: AuthSessionDep,
    admin: AdminUser,
    settings: SettingsDep,
) -> InvitationOut:
    svc = InvitationService(session)
    inv = await svc.create(
        created_by_id=admin.id,
        email=payload.email,
        note=payload.note,
        ttl_days=payload.ttl_days,
    )
    return InvitationOut.from_model(inv, settings.frontend_base_url)


@router.get("/admin/invitations", response_model=list[InvitationOut])
async def list_invitations(
    session: AuthSessionDep,
    admin: AdminUser,
    settings: SettingsDep,
) -> list[InvitationOut]:
    svc = InvitationService(session)
    invs = await svc.list_all()
    return [InvitationOut.from_model(i, settings.frontend_base_url) for i in invs]


@router.post(
    "/admin/invitations/{invitation_id}/revoke",
    response_model=InvitationOut,
)
async def revoke_invitation(
    invitation_id: UUID,
    session: AuthSessionDep,
    admin: AdminUser,
    settings: SettingsDep,
) -> InvitationOut:
    svc = InvitationService(session)
    inv = await svc.revoke(invitation_id)
    if inv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return InvitationOut.from_model(inv, settings.frontend_base_url)


@router.get("/invitations/{token}", response_model=InvitationPublicOut)
async def get_public_invitation(
    token: str,
    session: AuthSessionDep,
) -> InvitationPublicOut:
    """Public endpoint so /signup can prefill the email and show expiry."""
    svc = InvitationService(session)
    inv = await svc.get_by_token(token)
    if inv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return InvitationPublicOut(
        email=inv.email,
        expires_at=inv.expires_at,
        state=invitation_state(inv),
    )
