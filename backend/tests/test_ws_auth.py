import pytest

EMAIL = "ws@example.com"
PASSWORD = "hunter2hunter2"


class FakeWS:
    def __init__(self, cookies: dict[str, str] | None = None, origin: str | None = None):
        self.cookies = cookies or {}
        self.headers = {"origin": origin} if origin else {}
        self.accepted = False
        self.closed_code: int | None = None
        self._handshake: dict | None = None

    async def accept(self) -> None:
        self.accepted = True

    async def close(self, code: int) -> None:
        self.closed_code = code

    def queue_handshake(self, msg: dict) -> None:
        self._handshake = msg

    async def receive_json(self) -> dict:
        assert self._handshake is not None
        return self._handshake


async def _register(client, seed_invite, app_settings) -> None:
    app_settings(INITIAL_OWNER_EMAIL="")
    invite = await seed_invite(email=None)
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": EMAIL,
            "password": PASSWORD,
            "display_name": "WS",
            "invite_token": invite,
        },
    )
    assert r.status_code == 201, r.text


async def _cookie(client) -> str:
    r = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": EMAIL, "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 204
    return r.headers["set-cookie"].split(";")[0].split("=", 1)[1]


async def _bearer(client) -> str:
    r = await client.post(
        "/api/v1/auth/bearer/login",
        data={"username": EMAIL, "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_cookie_still_authenticates(client, seed_invite, app_settings):
    from klara.config import get_settings
    from klara.pronunciation.ws_auth import authenticate_ws

    await _register(client, seed_invite, app_settings)
    settings = get_settings()
    ws = FakeWS(cookies={settings.auth_cookie_name: await _cookie(client)})
    user = await authenticate_ws(ws, settings)
    assert user is not None and user.email == EMAIL


@pytest.mark.asyncio
async def test_bearer_token_authenticates(client, seed_invite, app_settings):
    from klara.config import get_settings
    from klara.pronunciation.ws_auth import authenticate_ws

    await _register(client, seed_invite, app_settings)
    token = await _bearer(client)
    user = await authenticate_ws(FakeWS(), get_settings(), token=token)
    assert user is not None and user.email == EMAIL


@pytest.mark.asyncio
async def test_revoked_bearer_token_is_rejected(client, seed_invite, app_settings):
    from klara.config import get_settings
    from klara.pronunciation.ws_auth import authenticate_ws

    await _register(client, seed_invite, app_settings)
    token = await _bearer(client)
    out = await client.post(
        "/api/v1/auth/bearer/logout", headers={"Authorization": f"Bearer {token}"}
    )
    assert out.status_code == 204
    assert await authenticate_ws(FakeWS(), get_settings(), token=token) is None


@pytest.mark.asyncio
async def test_stale_cookie_with_valid_token_authenticates(client, seed_invite, app_settings):
    """Una cookie presente pero inválida no debe tapar un token Bearer válido."""
    from klara.config import get_settings
    from klara.pronunciation.ws_auth import authenticate_ws

    await _register(client, seed_invite, app_settings)
    settings = get_settings()
    token = await _bearer(client)
    ws = FakeWS(cookies={settings.auth_cookie_name: "garbage"})
    user = await authenticate_ws(ws, settings, token=token)
    assert user is not None and user.email == EMAIL


@pytest.mark.asyncio
async def test_garbage_or_nothing_is_rejected(client):
    from klara.config import get_settings
    from klara.pronunciation.ws_auth import authenticate_ws

    settings = get_settings()
    assert await authenticate_ws(FakeWS(), settings) is None
    assert await authenticate_ws(FakeWS(), settings, token="x" * 43) is None


@pytest.mark.asyncio
async def test_stream_reads_handshake_before_auth_and_passes_token(client, monkeypatch):
    """Orden nuevo: origin-gate → accept → handshake → auth. Con token malo cierra
    con WS_CLOSE_AUTH; con auth OK y sin Azure cierra con WS_CLOSE_FAILURE."""
    from klara.pronunciation.streaming import WS_CLOSE_AUTH, WS_CLOSE_FAILURE
    from klara.routers import pronunciation as pron

    seen: dict[str, str | None] = {}

    async def fake_auth(websocket, settings, token=None):
        seen["token"] = token
        return None

    monkeypatch.setattr(pron, "authenticate_ws", fake_auth)
    ws = FakeWS(origin="http://localhost:5173")
    ws.queue_handshake({"reference_text": "Hallo", "language": "de", "token": "abc"})
    await pron.stream(ws)
    assert ws.accepted is True
    assert seen["token"] == "abc"
    assert ws.closed_code == WS_CLOSE_AUTH

    class _User:
        id = "00000000-0000-0000-0000-000000000001"
        is_active = True

    async def ok_auth(websocket, settings, token=None):
        return _User()

    monkeypatch.setattr(pron, "authenticate_ws", ok_auth)
    ws2 = FakeWS(origin="http://localhost:5173")
    ws2.queue_handshake({"reference_text": "Hallo", "language": "de"})
    await pron.stream(ws2)  # sin AZURE_SPEECH_KEY en tests → cierre "failure"
    assert ws2.closed_code == WS_CLOSE_FAILURE


@pytest.mark.asyncio
async def test_stream_rejects_non_string_token(client):
    from klara.pronunciation.streaming import WS_CLOSE_FAILURE
    from klara.routers import pronunciation as pron

    ws = FakeWS(origin="http://localhost:5173")
    ws.queue_handshake({"reference_text": "Hallo", "language": "de", "token": 42})
    await pron.stream(ws)
    assert ws.closed_code == WS_CLOSE_FAILURE
