import pytest

BAD = {"username": "nobody@example.com", "password": "definitely-wrong"}
FORM = {"Content-Type": "application/x-www-form-urlencoded"}


@pytest.fixture(autouse=True)
def _reset_login_limiter():
    from klara.ratelimit import login_limiter

    login_limiter.reset()
    yield
    login_limiter.reset()


def _xff(ip: str) -> dict[str, str]:
    # El peer del ASGITransport es 127.0.0.1 (loopback = proxy confiable), así
    # que client_ip toma el último hop del XFF: cada test elige su IP.
    return {**FORM, "X-Forwarded-For": ip}


@pytest.mark.asyncio
async def test_eleventh_login_attempt_is_429(client):
    for _ in range(10):
        r = await client.post("/api/v1/auth/jwt/login", data=BAD, headers=_xff("203.0.113.5"))
        assert r.status_code == 400  # credenciales malas, pero atendida
    r = await client.post("/api/v1/auth/jwt/login", data=BAD, headers=_xff("203.0.113.5"))
    assert r.status_code == 429


@pytest.mark.asyncio
async def test_other_ip_is_not_affected(client):
    for _ in range(11):
        await client.post("/api/v1/auth/jwt/login", data=BAD, headers=_xff("203.0.113.5"))
    r = await client.post("/api/v1/auth/jwt/login", data=BAD, headers=_xff("203.0.113.6"))
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_bearer_login_shares_the_bucket(client):
    for _ in range(10):
        await client.post("/api/v1/auth/jwt/login", data=BAD, headers=_xff("203.0.113.7"))
    r = await client.post("/api/v1/auth/bearer/login", data=BAD, headers=_xff("203.0.113.7"))
    assert r.status_code == 429


@pytest.mark.asyncio
async def test_logout_is_never_counted(client):
    for _ in range(12):
        r = await client.post("/api/v1/auth/jwt/logout", headers=_xff("203.0.113.8"))
        assert r.status_code == 401  # sin sesión, pero nunca 429


def test_window_resets():
    from klara.ratelimit import RateLimiter

    lim = RateLimiter(window_s=300, max_per_window=10)
    for _ in range(10):
        assert lim.hit("1.2.3.4", now=1000.0) is False
    assert lim.hit("1.2.3.4", now=1000.0) is True
    assert lim.hit("1.2.3.4", now=1000.0 + 301) is False


async def _register(client, seed_invite, app_settings, email: str) -> None:
    app_settings(INITIAL_OWNER_EMAIL="")
    invite = await seed_invite(email=None)
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "hunter2hunter2",
            "display_name": "Limit",
            "invite_token": invite,
        },
    )
    assert r.status_code == 201, r.text


@pytest.mark.asyncio
async def test_successful_login_clears_bucket(client, seed_invite, app_settings):
    email = "limit@example.com"
    await _register(client, seed_invite, app_settings, email)
    headers = _xff("203.0.113.20")

    for _ in range(9):
        r = await client.post("/api/v1/auth/jwt/login", data=BAD, headers=headers)
        assert r.status_code == 400

    good = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": email, "password": "hunter2hunter2"},
        headers=headers,
    )
    assert good.status_code == 204

    for _ in range(10):
        r = await client.post("/api/v1/auth/jwt/login", data=BAD, headers=headers)
        assert r.status_code == 400

    r = await client.post("/api/v1/auth/jwt/login", data=BAD, headers=headers)
    assert r.status_code == 429


@pytest.mark.asyncio
async def test_429_has_retry_after_and_localized_detail(client):
    headers_en = {**_xff("203.0.113.21"), "Accept-Language": "en"}
    for _ in range(10):
        await client.post("/api/v1/auth/jwt/login", data=BAD, headers=headers_en)
    r = await client.post("/api/v1/auth/jwt/login", data=BAD, headers=headers_en)
    assert r.status_code == 429
    assert r.headers["retry-after"] == "300"
    assert r.json()["detail"] == "Too many attempts. Wait a few minutes and try again."

    headers_es = {**_xff("203.0.113.22"), "Accept-Language": "es"}
    for _ in range(10):
        await client.post("/api/v1/auth/jwt/login", data=BAD, headers=headers_es)
    r2 = await client.post("/api/v1/auth/jwt/login", data=BAD, headers=headers_es)
    assert r2.status_code == 429
    assert r2.json()["detail"] == "Demasiados intentos. Espera unos minutos y vuelve a intentarlo."


@pytest.mark.asyncio
async def test_google_native_is_rate_limited(client, app_settings, monkeypatch):
    app_settings(GOOGLE_OAUTH_CLIENT_ID="web-client-id")
    from klara.auth import google_native

    def _raise(*_args, **_kwargs):
        raise google_native.InvalidGoogleToken("x")

    monkeypatch.setattr(google_native, "verify_google_id_token", _raise)
    headers = {"X-Forwarded-For": "203.0.113.23"}

    for _ in range(10):
        r = await client.post("/api/v1/auth/google/native", json={"id_token": "x"}, headers=headers)
        assert r.status_code == 400

    r = await client.post("/api/v1/auth/google/native", json={"id_token": "x"}, headers=headers)
    assert r.status_code == 429
