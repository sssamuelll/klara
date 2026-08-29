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
