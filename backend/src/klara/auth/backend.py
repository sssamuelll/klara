from fastapi_users.authentication import AuthenticationBackend, CookieTransport, JWTStrategy

from klara.config import Settings, get_settings


def _make_backend(settings: Settings) -> AuthenticationBackend:
    cookie_transport = CookieTransport(
        cookie_name=settings.auth_cookie_name,
        cookie_max_age=settings.auth_cookie_max_age,
        cookie_secure=not settings.is_dev,
        cookie_httponly=True,
        cookie_samesite="strict",
    )

    def get_jwt_strategy() -> JWTStrategy:
        return JWTStrategy(
            secret=settings.auth_jwt_secret,
            lifetime_seconds=settings.auth_cookie_max_age,
        )

    return AuthenticationBackend(
        name="cookie-jwt",
        transport=cookie_transport,
        get_strategy=get_jwt_strategy,
    )


auth_backend = _make_backend(get_settings())
