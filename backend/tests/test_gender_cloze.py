"""Gender cloze: evidence table, deterministic build, serve, server-side grading."""

import uuid

import pytest

from klara.models import GenderAttempt, VocabItem
from klara.models.enums import PartOfSpeech


@pytest.mark.asyncio
async def test_gender_attempt_roundtrips(db_session):
    from klara.models import User
    from klara.models.enums import CEFRLevel

    u = User(
        id=uuid.uuid4(),
        email=f"ga-{uuid.uuid4().hex[:6]}@k.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="GA",
        level=CEFRLevel.A1,
        native_language="es",
        target_language="de",
    )
    v = VocabItem(
        id=uuid.uuid4(),
        language="de",
        lemma=f"Tisch{uuid.uuid4().hex[:6]}",
        pos=PartOfSpeech.NOUN,
        gender="der",
        gender_source="oracle",
    )
    db_session.add_all([u, v])
    await db_session.flush()
    db_session.add(
        GenderAttempt(
            id=uuid.uuid4(),
            user_id=u.id,
            vocab_item_id=v.id,
            picked_article="die",
            was_correct=False,
        )
    )
    await db_session.commit()

    from sqlalchemy import select

    row = (
        await db_session.execute(select(GenderAttempt).where(GenderAttempt.user_id == u.id))
    ).scalar_one()
    assert row.picked_article == "die" and row.was_correct is False
