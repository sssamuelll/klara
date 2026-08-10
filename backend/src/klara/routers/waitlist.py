import ipaddress
import time
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


# ponytail: rate limit in-memory por proceso (un worker en prod; se resetea al
# reiniciar) y single-hop XFF (confía en el último hop si el peer inmediato es
# el proxy del host). Si hay N workers, cadena de proxies, o abuso real:
# slowapi con forwarded-allow-ips, ver TODO de main.py:147.
_WINDOW_S = 3600
_MAX_PER_WINDOW = 10
_hits: dict[str, tuple[int, float]] = {}


def _client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    xff = request.headers.get("x-forwarded-for")
    if not xff:
        return peer
    try:
        peer_addr = ipaddress.ip_address(peer)
    except ValueError:
        return peer
    if not (peer_addr.is_loopback or peer_addr.is_private):
        return peer
    candidate = xff.split(",")[-1].strip()
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return peer
    return candidate


def _rate_limited(ip: str, now: float | None = None) -> bool:
    t = now if now is not None else time.monotonic()
    count, start = _hits.get(ip, (0, t))
    if t - start > _WINDOW_S:
        count, start = 0, t
    count += 1
    _hits[ip] = (count, start)
    return count > _MAX_PER_WINDOW


@router.post("/waitlist", response_model=WaitlistOut)
async def join_waitlist(
    payload: WaitlistIn, request: Request, session: AuthSessionDep
) -> WaitlistOut:
    ip = _client_ip(request)
    if _rate_limited(ip):
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
