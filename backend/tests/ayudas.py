"""Ayudas compartidas por los tests de Klara en tres idiomas."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from klara.models import User
from klara.models.enums import CEFRLevel

PASSWORD = "hunter2hunter2"


async def crear_usuario(
    db, *, target_language: str = "de", study_languages: list[str] | None = None
) -> User:
    u = User(
        id=uuid.uuid4(),
        email=f"u-{uuid.uuid4().hex[:8]}@klara.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="Samuel",
        level=CEFRLevel.A1,
        native_language="es",
        target_language=target_language,
        study_languages=study_languages,
    )
    db.add(u)
    await db.commit()
    return u


async def entrar(client, seed_invite, email: str) -> str:
    """Registra una cuenta por invitación, inicia sesión y devuelve la cookie."""
    token = await seed_invite(email=None)
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "invite_token": token},
    )
    assert r.status_code == 201, r.text
    r2 = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": email, "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r2.status_code == 204, r2.text
    return r2.headers["set-cookie"].split(";")[0]


async def usuario_por_email(db, email: str) -> User:
    return (await db.execute(select(User).where(User.email == email))).scalar_one()
