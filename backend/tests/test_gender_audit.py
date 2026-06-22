"""gender_caseb_report surfaces ONLY the suppressed Case-B disagreements
(detail present AND agreement=false AND is_exception=false), aggregated by
lemma, most frequent first. Case-A agreement, Case-C exception, and no-detail
rows are excluded."""

import uuid

import pytest

from klara.curriculum.gender_audit import gender_caseb_report
from klara.models import GenderAttempt, User, VocabItem
from klara.models.enums import CEFRLevel, PartOfSpeech


async def _user(db) -> uuid.UUID:
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
    db.add(u)
    await db.flush()
    return u.id


async def _noun(db, *, lemma, gender, gender_source="oracle") -> VocabItem:
    v = VocabItem(
        id=uuid.uuid4(),
        language="de",
        lemma=lemma,
        pos=PartOfSpeech.NOUN,
        gender=gender,
        gender_source=gender_source,
    )
    db.add(v)
    await db.flush()
    return v


def _detail(*, suffix, suffix_class, rule_gender, oracle_gender, agreement, is_exception):
    return {
        "suffix": suffix,
        "suffix_class": suffix_class,
        "rule_gender": rule_gender,
        "oracle_gender": oracle_gender,
        "agreement": agreement,
        "is_exception": is_exception,
    }


async def _attempt(db, *, uid, vid, picked, correct, detail):
    db.add(
        GenderAttempt(
            id=uuid.uuid4(),
            user_id=uid,
            vocab_item_id=vid,
            picked_article=picked,
            was_correct=correct,
            detail=detail,
        )
    )


@pytest.mark.asyncio
async def test_report_isolates_case_b(db_session):
    uid = await _user(db_session)
    # Case B: tendency disagreement (Mutter ends -er→der, but oracle die).
    mutter = await _noun(db_session, lemma=f"Mutter{uuid.uuid4().hex[:6]}", gender="die")
    await _attempt(
        db_session,
        uid=uid,
        vid=mutter.id,
        picked="der",
        correct=False,
        detail=_detail(
            suffix="er",
            suffix_class="tendency",
            rule_gender="der",
            oracle_gender="die",
            agreement=False,
            is_exception=False,
        ),
    )
    # Case A agreement → excluded.
    wohnung = await _noun(db_session, lemma=f"Wohnung{uuid.uuid4().hex[:6]}", gender="die")
    await _attempt(
        db_session,
        uid=uid,
        vid=wohnung.id,
        picked="die",
        correct=True,
        detail=_detail(
            suffix="ung",
            suffix_class="hard",
            rule_gender="die",
            oracle_gender="die",
            agreement=True,
            is_exception=False,
        ),
    )
    # Case C curated exception → excluded.
    reichtum = await _noun(db_session, lemma=f"Reichtum{uuid.uuid4().hex[:6]}", gender="der")
    await _attempt(
        db_session,
        uid=uid,
        vid=reichtum.id,
        picked="der",
        correct=True,
        detail=_detail(
            suffix="tum",
            suffix_class="hard",
            rule_gender="das",
            oracle_gender="der",
            agreement=False,
            is_exception=True,
        ),
    )
    # No detail (no suffix detected) → excluded.
    haus = await _noun(db_session, lemma=f"Haus{uuid.uuid4().hex[:6]}", gender="das")
    await _attempt(db_session, uid=uid, vid=haus.id, picked="das", correct=True, detail=None)
    await db_session.commit()

    rows = await gender_caseb_report(db_session)
    assert len(rows) == 1
    row = rows[0]
    assert row.lemma == mutter.lemma
    assert row.suffix == "er"
    assert row.suffix_class == "tendency"
    assert row.rule_gender == "der"
    assert row.oracle_gender == "die"
    assert row.gender_source == "oracle"
    assert row.attempts == 1
    assert row.users == 1
    assert row.cause_hint == "tendency-miss"


@pytest.mark.asyncio
async def test_report_aggregates_and_orders_by_frequency(db_session):
    u1 = await _user(db_session)
    u2 = await _user(db_session)
    # schwung: a HARD false positive (-ung→die, oracle der), 3 attempts / 2 users.
    schwung = await _noun(db_session, lemma=f"Schwung{uuid.uuid4().hex[:6]}", gender="der")
    schwung_detail = _detail(
        suffix="ung",
        suffix_class="hard",
        rule_gender="die",
        oracle_gender="der",
        agreement=False,
        is_exception=False,
    )
    for uid in (u1, u1, u2):
        await _attempt(
            db_session, uid=uid, vid=schwung.id, picked="die", correct=False, detail=schwung_detail
        )
    # mutter: a tendency miss, 1 attempt / 1 user.
    mutter = await _noun(db_session, lemma=f"Mutter{uuid.uuid4().hex[:6]}", gender="die")
    await _attempt(
        db_session,
        uid=u1,
        vid=mutter.id,
        picked="der",
        correct=False,
        detail=_detail(
            suffix="er",
            suffix_class="tendency",
            rule_gender="der",
            oracle_gender="die",
            agreement=False,
            is_exception=False,
        ),
    )
    await db_session.commit()

    rows = await gender_caseb_report(db_session)
    assert len(rows) == 2
    # Most frequent first.
    assert rows[0].lemma == schwung.lemma
    assert rows[0].attempts == 3
    assert rows[0].users == 2
    assert rows[0].cause_hint == "hard-disagreement"
    assert rows[1].lemma == mutter.lemma
    assert rows[1].attempts == 1
    assert rows[1].users == 1


@pytest.mark.asyncio
async def test_report_excludes_detail_missing_suffix(db_session):
    # Defensive: a malformed detail (agreement/is_exception present but no suffix)
    # cannot arise from reconcile_rule, but the suffix-not-null guard excludes it
    # rather than projecting a NULL suffix into CaseBRow.
    uid = await _user(db_session)
    v = await _noun(db_session, lemma=f"X{uuid.uuid4().hex[:6]}", gender="die")
    await _attempt(
        db_session,
        uid=uid,
        vid=v.id,
        picked="der",
        correct=False,
        detail={"agreement": False, "is_exception": False},
    )
    await db_session.commit()
    assert await gender_caseb_report(db_session) == []


@pytest.mark.asyncio
async def test_report_empty_when_no_disagreements(db_session):
    uid = await _user(db_session)
    # Only an agreement row exists.
    wohnung = await _noun(db_session, lemma=f"Wohnung{uuid.uuid4().hex[:6]}", gender="die")
    await _attempt(
        db_session,
        uid=uid,
        vid=wohnung.id,
        picked="die",
        correct=True,
        detail=_detail(
            suffix="ung",
            suffix_class="hard",
            rule_gender="die",
            oracle_gender="die",
            agreement=True,
            is_exception=False,
        ),
    )
    await db_session.commit()
    assert await gender_caseb_report(db_session) == []
