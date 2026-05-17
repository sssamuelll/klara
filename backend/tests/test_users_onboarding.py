import uuid
from datetime import UTC, datetime

import pytest

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
