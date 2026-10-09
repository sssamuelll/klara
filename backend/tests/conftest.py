import itertools
import os
import subprocess
import sys
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Test database URL — assumes a local Postgres reachable as the `german` user
# (provisioned by docker-compose, or by `pg_ctlcluster 16 main start` + the role
# documented in the README). Override TEST_DATABASE_URL to point elsewhere.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://german:german_dev_pw@localhost:5432/german_app_test",
)
SYNC_TEST_DATABASE_URL = TEST_DATABASE_URL.replace("+asyncpg", "+psycopg2").replace(
    "postgresql+psycopg2", "postgresql"
)

# Issue #81: the app + Alembic take a passwordless DSN plus an out-of-band
# DB_PASSWORD. Mirror that split for every settings-driven path (the `client`
# fixture → init_engine, and `_run_alembic`) so tests exercise the real prod
# contract. The direct test engines below keep the full DSN — they connect
# straight, not via Settings.
_test_url = make_url(TEST_DATABASE_URL)
TEST_DB_PASSWORD = _test_url.password or ""
TEST_DATABASE_URL_NO_PW = _test_url._replace(password=None).render_as_string(hide_password=False)

# Force settings + auth code paths to use the test DB and stable secrets BEFORE
# the app module is imported (config is loaded via lru_cache).
os.environ["DATABASE_URL"] = TEST_DATABASE_URL_NO_PW
os.environ["DB_PASSWORD"] = TEST_DB_PASSWORD
os.environ.setdefault("AUTH_JWT_SECRET", "test-secret-key-do-not-use-in-prod")
os.environ.setdefault("AUTH_COOKIE_NAME", "klara_session")
os.environ.setdefault("APP_ENV", "development")


def _run_alembic(cmd: list[str]) -> None:
    backend_dir = Path(__file__).resolve().parent.parent
    env = os.environ.copy()
    env["DATABASE_URL"] = TEST_DATABASE_URL_NO_PW
    env["DB_PASSWORD"] = TEST_DB_PASSWORD
    result = subprocess.run(
        ["uv", "run", "alembic", *cmd],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise RuntimeError(f"alembic {cmd} failed")


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _prepare_database():
    _run_alembic(["downgrade", "base"])
    _run_alembic(["upgrade", "head"])
    yield
    _run_alembic(["downgrade", "base"])


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables():
    """Reset auth tables (and dependents) between tests."""
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.connect() as conn:
        await conn.execute(
            text(
                "TRUNCATE audio_cache, access_tokens, illustrations, invitations, oauth_accounts, reviews, user_cards, "
                "story_views, study_sessions, stories, module_vocab, modules, "
                "gender_attempts, gender_lexicon, gender_l1_notes, pronunciation_diagnoses, "
                "waitlist_signups, users "
                "RESTART IDENTITY CASCADE"
            )
        )
        await conn.commit()
    await engine.dispose()
    yield


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    """login_limiter/waitlist_limiter are process-wide singletons (klara.ratelimit);
    without a per-test reset, cumulative login calls across unrelated test files
    (all from the same ASGITransport peer IP) trip the 429 and cascade failures."""
    from klara import ratelimit

    ratelimit.waitlist_limiter.reset()
    ratelimit.login_limiter.reset()


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    sessionmaker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with sessionmaker() as session:
        yield session


def _set_settings_env(**overrides: str | None) -> None:
    for k, v in overrides.items():
        if v is None and k in os.environ:
            del os.environ[k]
        elif v is not None:
            os.environ[k] = v


def _reset_settings_cache() -> None:
    from klara.config import get_settings

    get_settings.cache_clear()


@pytest.fixture
def app_settings():
    """
    Mutates env vars and resets the cached Settings singleton. Use to test
    owner-email and other config-dependent scenarios.
    """

    snapshot: dict[str, str | None] = {}

    def _apply(**overrides: str | None) -> None:
        for k, v in overrides.items():
            snapshot.setdefault(k, os.environ.get(k))
            if v is None and k in os.environ:
                del os.environ[k]
            elif v is not None:
                os.environ[k] = v
        _reset_settings_cache()

    yield _apply

    for k, original in snapshot.items():
        if original is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = original
    _reset_settings_cache()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    # Import inside fixture so env vars set at import-time take effect.
    from klara.config import get_settings
    from klara.db import dispose_engine, init_engine
    from klara.main import create_app

    settings = get_settings()
    init_engine(settings)
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await dispose_engine()


@pytest.fixture
def captured_emails(monkeypatch):
    """
    Replaces EmailService.send_verify / send_reset with capturing stubs so
    verify and reset flow tests can pull the token without parsing logs.
    Returns the same list that the stubs append to.
    """
    captured: list[dict[str, str]] = []

    async def fake_send_verify(self, user, token):  # type: ignore[no-untyped-def]
        captured.append({"kind": "verify", "to": user.email or "", "token": token})

    async def fake_send_reset(self, user, token):  # type: ignore[no-untyped-def]
        captured.append({"kind": "reset", "to": user.email or "", "token": token})

    from klara.auth.email import EmailService

    monkeypatch.setattr(EmailService, "send_verify", fake_send_verify)
    monkeypatch.setattr(EmailService, "send_reset", fake_send_reset)
    return captured


@pytest_asyncio.fixture
async def seed_invite(db_session: AsyncSession):
    """Returns a coroutine that seeds an active invitation row and returns its token."""
    from datetime import UTC, datetime, timedelta

    from klara.auth.invitations import generate_token
    from klara.models import Invitation, User
    from klara.models.enums import CEFRLevel

    async def _seed(*, email: str | None = None, ttl_days: int = 7) -> str:
        # The invite needs a creator FK — seed an admin user if none exists.
        admin = (
            (
                await db_session.execute(
                    __import__("sqlalchemy").select(User).where(User.is_superuser.is_(True))
                )
            )
            .scalars()
            .first()
        )
        if admin is None:
            admin = User(
                id=uuid.uuid4(),
                email=f"admin-{uuid.uuid4().hex[:6]}@klara.app",
                hashed_password="x",
                is_active=True,
                is_verified=True,
                is_superuser=True,
                display_name="Admin",
                level=CEFRLevel.A0,
                native_language="es",
                target_language="de",
            )
            db_session.add(admin)
            await db_session.flush()

        token = generate_token()
        inv = Invitation(
            id=uuid.uuid4(),
            token=token,
            email=email.lower() if email else None,
            note=None,
            created_by=admin.id,
            expires_at=datetime.now(UTC) + timedelta(days=ttl_days),
        )
        db_session.add(inv)
        await db_session.commit()
        return token

    return _seed


@pytest_asyncio.fixture
async def legacy_owner_with_story(db_session: AsyncSession):
    """Inserts a legacy user (email=NULL) plus an owned story — mimics pre-auth state."""
    from klara.models import Story, User
    from klara.models.enums import CEFRLevel

    user = User(
        id=uuid.uuid4(),
        email=None,
        hashed_password=None,
        is_active=True,
        is_verified=False,
        is_superuser=False,
        display_name="Samuel",
        level=CEFRLevel.A0,
        native_language="es",
        target_language="de",
    )
    db_session.add(user)
    await db_session.flush()

    story = Story(
        id=uuid.uuid4(),
        user_id=user.id,
        level=CEFRLevel.A0,
        target_language="de",
        native_language="es",
        title="Eine Geschichte",
        content={"sentences": [], "comprehension_questions": []},
        target_vocab_item_ids=[],
    )
    db_session.add(story)
    await db_session.commit()
    await db_session.refresh(user)
    return {"user_id": str(user.id), "story_id": str(story.id)}


@pytest_asyncio.fixture
async def seed_oauth_account(db_session):
    """Returns a coroutine that links an oauth_account row to an existing user."""
    from klara.models import OAuthAccount

    async def _seed(
        *,
        user_id,
        oauth_name: str = "google",
        account_id: str | None = None,
        account_email: str,
        access_token: str = "fake-access-token",
    ):
        row = OAuthAccount(
            id=uuid.uuid4(),
            user_id=user_id,
            oauth_name=oauth_name,
            account_id=account_id or uuid.uuid4().hex,
            account_email=account_email,
            access_token=access_token,
        )
        db_session.add(row)
        await db_session.commit()
        return row.id

    return _seed


def _voiced_wav_bytes(seconds: float = 1.2, level_dbfs: float = -20.0, rate: int = 16_000) -> bytes:
    """PCM 16-bit mono frames shaped like speech: a harmonic stack under a
    syllabic envelope. The gate measures voiced energy, so a flat tone or a
    stub like b"RIFFfake" gets rejected (or fails to parse) before the endpoint
    under test ever runs."""
    import numpy as np

    t = np.arange(round(seconds * rate)) / rate
    sig = sum(np.sin(2 * np.pi * 150.0 * k * t) / k for k in range(1, 12))
    sig = sig * (1.0 + 0.35 * np.sin(2 * np.pi * 4.0 * t))
    sig = sig / np.max(np.abs(sig))
    sig = sig * (10.0 ** (level_dbfs / 20.0) / float(np.sqrt(np.mean(sig**2))))
    return np.clip(sig * 32768.0, -32768, 32767).astype("<i2").tobytes()


@pytest.fixture
def gate_passing_transcode(tmp_path):
    """Drop-in for transcode_to_wav that emits real, gate-passing audio.

    Patch it at `klara.pronunciation.audio_quality.transcode_to_wav` — that is
    the name transcode_and_gate resolves, so the real quality gate still runs
    over the audio and the router path stays honest.
    """
    import wave

    counter = itertools.count()

    def _fake(src_bytes: bytes, *, sample_rate: int = 16_000) -> Path:
        # A fresh file per call: the gate may rewrite it in place, and the
        # caller unlinks it when the request finishes.
        out = tmp_path / f"take{next(counter)}.wav"
        with wave.open(str(out), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(sample_rate)
            handle.writeframes(_voiced_wav_bytes(rate=sample_rate))
        return out

    return _fake


@pytest.fixture
def catalogo_mini(tmp_path, monkeypatch):
    """El catálogo de juguete (tests/catalogo_mini.py), servido por get_catalogo()
    a todo el que lo pida durante el test, incluida la app de `client`."""
    from klara.catalogo.cargar import get_catalogo
    from tests.catalogo_mini import escribir_catalogo_mini

    raiz = escribir_catalogo_mini(tmp_path / "mapas")
    monkeypatch.setenv("KLARA_MAPAS_DIR", str(raiz))
    get_catalogo.cache_clear()
    yield get_catalogo()
    get_catalogo.cache_clear()
