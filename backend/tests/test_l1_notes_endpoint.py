"""GET /stories/{id}/gender/l1-notes: oracle-gated display gender, case-insensitive
lemma match, story-L1-keyed, owner-gated. Lemmas are uuid-suffixed (vocab_items is
not truncated); gender_l1_notes IS truncated, so seeds never collide across tests."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from klara.auth.users import current_active_user
from klara.curriculum.l1_notes import L1NoteRow, load_l1_notes
from klara.dependencies import db_session as db_session_dep
from klara.main import create_app
from klara.models import Story, User, VocabItem
from klara.models.enums import CEFRLevel, PartOfSpeech


async def _user(db, *, native_language="es"):
    u = User(
        id=uuid.uuid4(),
        email=f"l1-{uuid.uuid4().hex[:6]}@k.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="L1",
        level=CEFRLevel.A1,
        native_language=native_language,
        target_language="de",
    )
    db.add(u)
    await db.flush()
    return u


async def _noun(db, *, lemma, gender, gender_source="oracle", language="de", pos=PartOfSpeech.NOUN):
    v = VocabItem(
        id=uuid.uuid4(),
        language=language,
        lemma=lemma,
        pos=pos,
        gender=gender,
        gender_source=gender_source,
    )
    db.add(v)
    await db.flush()
    return v


async def _story(db, *, user, vocab_ids, native_language="es"):
    s = Story(
        id=uuid.uuid4(),
        user_id=user.id,
        level=CEFRLevel.A1,
        target_language="de",
        native_language=native_language,
        title="t",
        content={"sentences": [], "comprehension_questions": []},
        target_vocab_item_ids=list(vocab_ids),
    )
    db.add(s)
    await db.flush()
    return s


async def _get_notes(db, user, story_id):
    app = create_app()
    app.dependency_overrides[current_active_user] = lambda: user
    app.dependency_overrides[db_session_dep] = lambda: db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        return await ac.get(f"/api/v1/stories/{story_id}/gender/l1-notes")


@pytest.mark.asyncio
async def test_returns_oracle_resolved_notes(db_session):
    lemma = f"Auto{uuid.uuid4().hex[:6]}"
    u = await _user(db_session)
    v = await _noun(db_session, lemma=lemma, gender="das")
    s = await _story(db_session, user=u, vocab_ids=[v.id])
    await load_l1_notes(
        db_session, rows=[L1NoteRow(lemma=lemma, l1_language="es", note="trampa coche")]
    )
    await db_session.commit()
    resp = await _get_notes(db_session, u, s.id)
    assert resp.status_code == 200, resp.text
    notes = resp.json()["notes"]
    assert notes == [{"lemma": lemma, "gender": "das", "note": "trampa coche"}]


@pytest.mark.asyncio
async def test_llm_gendered_word_with_note_is_dropped(db_session):
    lemma = f"Auto{uuid.uuid4().hex[:6]}"
    u = await _user(db_session)
    v = await _noun(db_session, lemma=lemma, gender="das", gender_source="llm")
    s = await _story(db_session, user=u, vocab_ids=[v.id])
    await load_l1_notes(db_session, rows=[L1NoteRow(lemma=lemma, l1_language="es", note="x")])
    await db_session.commit()
    resp = await _get_notes(db_session, u, s.id)
    assert resp.status_code == 200, resp.text
    assert resp.json()["notes"] == []


@pytest.mark.asyncio
async def test_case_insensitive_lemma_match(db_session):
    base = f"Auto{uuid.uuid4().hex[:6]}"  # seed casing
    u = await _user(db_session)
    v = await _noun(db_session, lemma=base.lower(), gender="das")  # drifted lowercase VocabItem
    s = await _story(db_session, user=u, vocab_ids=[v.id])
    await load_l1_notes(db_session, rows=[L1NoteRow(lemma=base, l1_language="es", note="trampa")])
    await db_session.commit()
    resp = await _get_notes(db_session, u, s.id)
    assert resp.status_code == 200, resp.text
    notes = resp.json()["notes"]
    assert len(notes) == 1
    assert notes[0]["lemma"] == base  # display uses the seed's capitalized lemma


@pytest.mark.asyncio
async def test_non_canonical_story_l1_still_matches(db_session):
    lemma = f"Auto{uuid.uuid4().hex[:6]}"
    u = await _user(db_session, native_language="ES")
    v = await _noun(db_session, lemma=lemma, gender="das")
    s = await _story(db_session, user=u, vocab_ids=[v.id], native_language="ES")
    await load_l1_notes(db_session, rows=[L1NoteRow(lemma=lemma, l1_language="es", note="trampa")])
    await db_session.commit()
    resp = await _get_notes(db_session, u, s.id)
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["notes"]) == 1


@pytest.mark.asyncio
async def test_empty_when_no_seed(db_session):
    lemma = f"Auto{uuid.uuid4().hex[:6]}"
    u = await _user(db_session)
    v = await _noun(db_session, lemma=lemma, gender="das")
    s = await _story(db_session, user=u, vocab_ids=[v.id])  # no seed loaded
    await db_session.commit()
    resp = await _get_notes(db_session, u, s.id)
    assert resp.status_code == 200, resp.text
    assert resp.json()["notes"] == []


@pytest.mark.asyncio
async def test_empty_when_no_target_words(db_session):
    u = await _user(db_session)
    s = await _story(db_session, user=u, vocab_ids=[])
    await db_session.commit()
    resp = await _get_notes(db_session, u, s.id)
    assert resp.status_code == 200, resp.text
    assert resp.json()["notes"] == []


@pytest.mark.asyncio
async def test_owner_gated_404(db_session):
    lemma = f"Auto{uuid.uuid4().hex[:6]}"
    owner = await _user(db_session)
    other = await _user(db_session)
    v = await _noun(db_session, lemma=lemma, gender="das")
    s = await _story(db_session, user=owner, vocab_ids=[v.id])
    await db_session.commit()
    resp = await _get_notes(db_session, other, s.id)  # not the owner
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_non_es_story_l1_returns_empty(db_session):
    # A non-Spanish learner never gets Spanish prose: a fr story + only es seeds -> [].
    lemma = f"Auto{uuid.uuid4().hex[:6]}"
    u = await _user(db_session, native_language="fr")
    v = await _noun(db_session, lemma=lemma, gender="das")
    s = await _story(db_session, user=u, vocab_ids=[v.id], native_language="fr")
    await load_l1_notes(db_session, rows=[L1NoteRow(lemma=lemma, l1_language="es", note="trampa")])
    await db_session.commit()
    resp = await _get_notes(db_session, u, s.id)
    assert resp.status_code == 200, resp.text
    assert resp.json()["notes"] == []


@pytest.mark.asyncio
async def test_non_noun_dropped(db_session):
    # The pos==NOUN guard: a verb with a matching seed is dropped even if oracle-sourced.
    lemma = f"laufen{uuid.uuid4().hex[:6]}"
    u = await _user(db_session)
    v = await _noun(
        db_session, lemma=lemma, gender=None, gender_source="oracle", pos=PartOfSpeech.VERB
    )
    s = await _story(db_session, user=u, vocab_ids=[v.id])
    await load_l1_notes(db_session, rows=[L1NoteRow(lemma=lemma, l1_language="es", note="x")])
    await db_session.commit()
    resp = await _get_notes(db_session, u, s.id)
    assert resp.status_code == 200, resp.text
    assert resp.json()["notes"] == []


@pytest.mark.asyncio
async def test_integration_real_seed_surfaces_for_a1_noun(db_session):
    # Lock the shipped seed against the real A1 corpus: the actual "Auto" seed
    # surfaces for an oracle "Auto" (das) noun (load_de_modules seeds Auto/das;
    # story_gen stamps gender_source="oracle" in prod once the lexicon is loaded).
    from klara.scripts.load_de_l1_notes import _ES_NOTES

    rows = [L1NoteRow(lemma=lemma, l1_language="es", note=note) for lemma, note in _ES_NOTES]
    await load_l1_notes(db_session, rows=rows)
    u = await _user(db_session)
    v = await _noun(db_session, lemma="Auto", gender="das")
    s = await _story(db_session, user=u, vocab_ids=[v.id])
    await db_session.commit()
    resp = await _get_notes(db_session, u, s.id)
    assert resp.status_code == 200, resp.text
    notes = resp.json()["notes"]
    assert len(notes) == 1
    assert notes[0]["lemma"] == "Auto"
    assert notes[0]["gender"] == "das"
    assert "coche" in notes[0]["note"]
