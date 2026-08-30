"""Verificación del ID token de Google que entrega el Credential Manager del app
nativo (spec android §2.2).

Sin dependencia nueva: pyjwt[crypto] ya viene con fastapi-users. La firma se
comprueba contra el JWKS público de Google; la audiencia es el Web Client ID
(el mismo que usa el flujo del navegador), porque el plugin del app se
inicializa con ese id y Google lo pone en `aud`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import jwt
import structlog
from jwt import PyJWKClient

GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = frozenset({"https://accounts.google.com", "accounts.google.com"})

log = structlog.get_logger(__name__)

_jwks_client: PyJWKClient | None = None


class InvalidGoogleToken(Exception):
    """Firma, audiencia, emisor, expiración o email no verificado."""


@dataclass(frozen=True)
class GoogleClaims:
    sub: str
    email: str
    exp: int


def _signing_key(id_token: str) -> Any:
    """Clave pública de Google para este token (cacheada por PyJWKClient).
    Separada para que los tests la sustituyan por una clave local."""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(GOOGLE_JWKS_URL, cache_keys=True, timeout=5)
    return _jwks_client.get_signing_key_from_jwt(id_token).key


def verify_google_id_token(id_token: str, audience: str) -> GoogleClaims:
    try:
        key = _signing_key(id_token)
        claims = jwt.decode(
            id_token,
            key,
            algorithms=["RS256"],
            audience=audience,
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
        )
    except jwt.exceptions.PyJWKClientError as e:
        # Fallo de transporte (red/DNS/timeout) al refrescar el JWKS, no una
        # firma inválida — distinto del resto de fallos de claims, que se
        # quedan silenciosos como hasta ahora.
        log.warning("google_native.jwks_unavailable", error=str(e))
        raise InvalidGoogleToken(str(e)) from e
    except jwt.PyJWTError as e:
        raise InvalidGoogleToken(str(e)) from e
    # `issuer=` de pyjwt acepta lista solo en versiones recientes; comparar a mano
    # es una línea y no depende de la versión.
    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise InvalidGoogleToken("issuer")
    email = claims.get("email")
    if claims.get("email_verified") is not True or not email:
        raise InvalidGoogleToken("email not verified")
    return GoogleClaims(sub=str(claims["sub"]), email=str(email), exp=int(claims["exp"]))
