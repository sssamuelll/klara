import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from klara.models import User
from klara.models.enums import CEFRLevel


@pytest.mark.asyncio
async def test_user_onboarding_completed_at_roundtrips(db_session):
    """Column defaults to NULL and round-trips a timezone-aware datetime."""
    user = User(
        id=uuid.uuid4(),
        email=None,
        hashed_password=None,
        is_active=True,
        is_verified=False,
        is_superuser=False,
        display_name="Tester",
        level=CEFRLevel.A0,
        native_language="es",
        target_language="de",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.onboarding_completed_at is None

    ts = datetime.now(UTC)
    user.onboarding_completed_at = ts
    await db_session.commit()
    await db_session.refresh(user)
    assert user.onboarding_completed_at is not None
    # Round-trips a tz-aware datetime (Postgres stores in UTC):
    assert user.onboarding_completed_at.tzinfo is not None


@pytest.mark.asyncio
async def test_seed_oauth_account_fixture_works(db_session, seed_oauth_account):
    """Fixture sanity: creates an oauth_account row linked to a fresh user."""
    user = User(
        id=uuid.uuid4(),
        email="oauth@example.com",
        hashed_password=None,
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="Oauth Tester",
        level=CEFRLevel.A0,
        native_language="es",
        target_language="de",
    )
    db_session.add(user)
    await db_session.flush()

    oa_id = await seed_oauth_account(
        user_id=user.id,
        account_email="oauth@example.com",
    )
    from klara.models import OAuthAccount
    row = (
        await db_session.execute(
            select(OAuthAccount).where(OAuthAccount.id == oa_id)
        )
    ).scalar_one()
    assert row.oauth_name == "google"
    assert row.user_id == user.id
