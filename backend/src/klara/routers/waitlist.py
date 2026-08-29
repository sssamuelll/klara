from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from klara.auth.db import AuthSessionDep
from klara.auth.users import current_admin_user
from klara.models.user import User
from klara.models.waitlist import WaitlistSignup
from klara.ratelimit import client_ip, waitlist_limiter

router = APIRouter()

AdminUser = Annotated[User, Depends(current_admin_user)]


class WaitlistIn(BaseModel):
    email: EmailStr
    locale: str | None = Field(default=None, max_length=8)


class WaitlistOut(BaseModel):
    ok: bool = True


class WaitlistRowOut(BaseModel):
    id: UUID
    email: EmailStr
    locale: str | None
    created_at: datetime
    invited_at: datetime | None

    model_config = {"from_attributes": True}


@router.post("/waitlist", response_model=WaitlistOut)
async def join_waitlist(
    payload: WaitlistIn, request: Request, session: AuthSessionDep
) -> WaitlistOut:
    if waitlist_limiter.hit(client_ip(request)):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS)
    email = payload.email.strip().lower()
    existing = await session.scalar(select(WaitlistSignup).where(WaitlistSignup.email == email))
    if existing is None:
        session.add(WaitlistSignup(email=email, locale=payload.locale))
        try:
            await session.commit()
        except IntegrityError:
            # Carrera entre dos POST del mismo correo: el segundo pierde y da igual.
            await session.rollback()
    # Respuesta idéntica exista o no: sin enumeración de correos.
    return WaitlistOut()


@router.get("/admin/waitlist", response_model=list[WaitlistRowOut])
async def list_waitlist(session: AuthSessionDep, admin: AdminUser) -> list[WaitlistRowOut]:
    rows = await session.scalars(select(WaitlistSignup).order_by(WaitlistSignup.created_at.desc()))
    return [WaitlistRowOut.model_validate(r) for r in rows]


@router.post("/admin/waitlist/{signup_id}/invited", response_model=WaitlistRowOut)
async def mark_invited(
    signup_id: UUID, session: AuthSessionDep, admin: AdminUser
) -> WaitlistRowOut:
    row = await session.get(WaitlistSignup, signup_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    row.invited_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(row)
    return WaitlistRowOut.model_validate(row)
