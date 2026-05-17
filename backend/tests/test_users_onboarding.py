import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from klara.models import User
from klara.models.enums import CEFRLevel


@pytest.mark.asyncio
async def test_user_model_has_onboarding_completed_at_nullable(db_session):
    """La columna existe, default NULL, acepta inserción sin valor."""
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
