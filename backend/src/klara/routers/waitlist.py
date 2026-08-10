import time
from typing import Annotated

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


# ponytail: rate limit in-memory por proceso (un worker en prod; se resetea al
# reiniciar). Si hay N workers o abuso real: slowapi, ver TODO de main.py:147.
_WINDOW_S = 3600
_MAX_PER_WINDOW = 10
_hits: dict[str, tuple[int, float]] = {}


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
    ip = request.client.host if request.client else "unknown"
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
