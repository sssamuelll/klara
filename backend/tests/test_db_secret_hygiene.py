"""Regression guard for issue #81 — the Postgres password must never ride
inside the DSN string.

A cleartext credential in a connection string can leak via ``repr(engine)``,
tracebacks that interpolate the URL, or any direct log of ``settings.database_url``.
The password is split out of ``database_url`` into a ``SecretStr`` and injected
out-of-band via ``connect_args`` so it never appears in the engine URL, and the
default is empty so a missing ``DB_PASSWORD`` fails closed.
"""

from sqlalchemy import make_url, text

from klara.config import Settings, get_settings
from klara.db import dispose_engine, init_engine


def test_database_url_default_carries_no_embedded_password():
    # The hardcoded default is exactly what CodeQL flags as a clear-text
    # credential. It must be passwordless.
    default = Settings.model_fields["database_url"].default
    assert make_url(default).password is None


def test_settings_expose_a_separate_db_password():
    assert "db_password" in Settings.model_fields


def test_db_connect_args_injects_password_when_dsn_is_passwordless():
    s = Settings(
        database_url="postgresql+asyncpg://german@localhost:5432/db",
        db_password="secret",
    )
    assert s.db_connect_args == {"password": "secret"}


def test_db_connect_args_respects_a_password_already_in_the_dsn():
    # Backward-compat: a full DSN (e.g. a CI job that sets
    # DATABASE_URL=user:pass@host) keeps its own credential — never overridden.
    s = Settings(
        database_url="postgresql+asyncpg://german:inurl@localhost:5432/db",
        db_password="other",
    )
    assert s.db_connect_args == {}


def test_db_password_default_is_empty_so_missing_config_fails_closed():
    # No baked dev credential in source: the field default is empty, so a
    # passwordless DSN with no DB_PASSWORD yields no connect_args and the
    # connection fails closed instead of silently using a fallback password.
    assert Settings.model_fields["db_password"].default.get_secret_value() == ""


def test_db_connect_args_empty_when_no_password_available():
    s = Settings(
        database_url="postgresql+asyncpg://german@localhost:5432/db",
        db_password="",
    )
    assert s.db_connect_args == {}


def test_db_connect_args_overrides_an_empty_in_url_password():
    # A stray trailing colon yields an empty (not absent) in-URL password — it
    # is not a usable credential, so the configured DB_PASSWORD still wins.
    s = Settings(
        database_url="postgresql+asyncpg://german:@localhost:5432/db",
        db_password="secret",
    )
    assert s.db_connect_args == {"password": "secret"}


def test_db_password_is_masked_in_settings_repr_and_dump():
    # db_password is a SecretStr, so the credential stays out of repr() and
    # model_dump() — the same leak-via-logs/tracebacks vector issue #81 names.
    s = Settings(db_password="topsecret-xyz")
    assert "topsecret-xyz" not in repr(s)
    assert "topsecret-xyz" not in str(s.model_dump())


async def test_init_engine_keeps_the_password_out_of_the_engine_url():
    # conftest has already split the test DSN into a passwordless DATABASE_URL
    # plus DB_PASSWORD, mirroring the prod contract. The live engine URL must
    # carry no password (so repr/rows can never leak it), yet still connect.
    get_settings.cache_clear()
    engine = init_engine(get_settings())
    try:
        assert engine.url.password is None
        async with engine.connect() as conn:
            assert (await conn.execute(text("select 1"))).scalar() == 1
    finally:
        await dispose_engine()
        get_settings.cache_clear()
