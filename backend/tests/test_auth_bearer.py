import pytest
from sqlalchemy import select


@pytest.mark.asyncio
async def test_access_token_row_roundtrip(db_session, seed_invite):
    """La tabla existe (migración 0022) y el modelo mapea users.id, no user.id."""
    from klara.models import AccessToken, User

    await seed_invite()  # siembra un admin: nos sirve de dueño del token
    owner = (await db_session.execute(select(User))).scalars().first()
    assert owner is not None

    token = "a" * 43
    db_session.add(AccessToken(token=token, user_id=owner.id))
    await db_session.commit()

    row = await db_session.get(AccessToken, token)
    assert row is not None
    assert row.user_id == owner.id
    assert row.created_at.tzinfo is not None
