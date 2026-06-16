"""generate_story recibe target_lemmas y filtra target_vocab_item_ids a los lemas
realmente cubiertos por la historia (honestidad de cobertura)."""

import uuid
from datetime import UTC, datetime

import pytest

from klara.models import VocabItem
from klara.models.enums import CEFRLevel, PartOfSpeech
from klara.services.story_gen import generate_story


class _FakeLLM:
    """Devuelve una historia fija: contiene 'Haus' (cubierto) pero NO 'Brücke'."""

    def __init__(self):
        self.provider = "fake"
        self.model = "fake"
        self.cost_usd = 0.0

    async def complete(self, **kwargs):
        import json
        from types import SimpleNamespace

        data = {
            "title": "Das Haus",
            "sentences": [
                {
                    "target": "Das Haus ist groß.",
                    "native": "La casa es grande.",
                    "new_words": ["Haus"],
                    "breakdown": [{"word": "Haus", "translation": "casa", "pos": "noun"}],
                }
            ],
            "comprehension_questions": [],
            "target_words": [
                {
                    "lemma": "Haus",
                    "pos": "noun",
                    "translation": "casa",
                    "example_target": "Das Haus.",
                },
                {
                    "lemma": "Brücke",
                    "pos": "noun",
                    "translation": "puente",
                    "example_target": "Die Brücke.",
                },
            ],
        }
        return SimpleNamespace(
            content=json.dumps(data), provider="fake", model="fake", cost_usd=0.0
        )


async def _user_id(db) -> uuid.UUID:
    from klara.models import User

    u = User(
        id=uuid.uuid4(),
        email=f"g-{uuid.uuid4().hex[:6]}@k.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="G",
        level=CEFRLevel.A1,
        native_language="es",
        target_language="de",
    )
    db.add(u)
    await db.flush()
    return u.id


@pytest.mark.asyncio
async def test_uncovered_target_word_dropped_from_story(db_session):
    uid = await _user_id(db_session)
    result = await generate_story(
        db_session,
        _FakeLLM(),
        user_id=uid,
        level=CEFRLevel.A1,
        target_language="de",
        native_language="es",
        learning_context=None,
        topic=None,
        model=None,
        target_lemmas=["Haus", "Brücke"],
    )
    # 'Brücke' fue pedida y devuelta por el LLM, pero NO aparece en la historia →
    # se cae de target_vocab_item_ids (no afirmamos enseñarla).
    kept = (
        (
            await db_session.execute(
                __import__("sqlalchemy")
                .select(VocabItem.lemma)
                .where(VocabItem.id.in_(result.story.target_vocab_item_ids))
            )
        )
        .scalars()
        .all()
    )
    assert "Haus" in kept
    assert "Brücke" not in kept
    # La respuesta (target_words) tampoco debe afirmar enseñar lo no cubierto:
    returned = [w.lemma for w in result.target_words]
    assert "Haus" in returned and "Brücke" not in returned


def test_serialize_exposes_frequency_rank_and_note():
    from klara.models import Story as StoryModel
    from klara.routers.stories import _serialize_story

    v = VocabItem(
        id=uuid.uuid4(),
        language="de",
        lemma="Haus",
        pos=PartOfSpeech.NOUN,
        frequency_rank=10,
        cefr_level=CEFRLevel.A1,
        translations={"es": "casa"},
    )
    story = StoryModel(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        level=CEFRLevel.A1,
        target_language="de",
        native_language="es",
        title="Das Haus",
        content={"sentences": [], "comprehension_questions": []},
        target_vocab_item_ids=[v.id],
        created_at=datetime.now(UTC),  # StoryOut.created_at es datetime requerido; el modelo
        # solo tiene server_default (sin default Python), así que un Story() en memoria
        # sin flush deja created_at=None → ValidationError. Lo seteamos en el fixture.
    )
    out = _serialize_story(story, [v], "es")
    assert out.target_words[0].frequency_rank == 10
    assert out.curriculum_note is not None and "Haus" in out.curriculum_note
