"""Google Sign-In del app nativo: ID token → sesión Bearer (spec android §2.2).

Entra por el MISMO UserManager.oauth_callback que el callback del navegador:
ahí viven la regla de invitación y la adopción del dueño legacy. Nunca se crea
el usuario a mano.
"""

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from klara.auth import google_native
from klara.auth.bearer import StrategyDep
from klara.dependencies import LocaleDep, SettingsDep, UserManagerDep
from klara.i18n import t

router = APIRouter(prefix="/auth/google", tags=["auth"])


class GoogleNativeIn(BaseModel):
    id_token: str


class BearerOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/native", response_model=BearerOut)
async def google_native_login(
    payload: GoogleNativeIn,
    request: Request,
    settings: SettingsDep,
    locale: LocaleDep,
    user_manager: UserManagerDep,
    strategy: StrategyDep,
) -> BearerOut:
    if not settings.google_oauth_client_id:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    try:
        claims = google_native.verify_google_id_token(
            payload.id_token, settings.google_oauth_client_id
        )
    except google_native.InvalidGoogleToken:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("auth.google_native.invalid", locale),
        ) from None
    # access_token = el propio id_token: la columna de oauth_accounts es NOT NULL
    # y este flujo no tiene access token de Google (decisión deliberada, spec §2.2).
    user = await user_manager.oauth_callback(
        "google",
        payload.id_token,
        claims.sub,
        claims.email,
        expires_at=claims.exp,
        request=request,
        associate_by_email=True,
        is_verified_by_default=True,
    )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("auth.google_native.invalid", locale),
        )
    token = await strategy.write_token(user)
    return BearerOut(access_token=token)
