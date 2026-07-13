"""services.story_lint: flags ONLY provable gender-article errors (sub-flag by design)."""

import json

import pytest

from klara.curriculum.gender_lex import GenderRow, load_gender_lexicon
from klara.llm.base import LLMResponse
from klara.models.enums import CEFRLevel
from klara.services.story_gen import generate_story_draft
from klara.services.story_lint import gender_article_violations


class _FakeLLM:
    """Devuelve un payload fijo; cumple el Protocol de complete()."""

    def __init__(self, payload: dict):
        self._payload = payload

    async def complete(self, **kwargs):
        return LLMResponse(content=json.dumps(self._payload), model="fake", provider="fake")

    async def stream(self, **kwargs):  # pragma: no cover — protocol completeness
        raise NotImplementedError


def _content(*targets: str) -> dict:
    return {
        "sentences": [{"target": t, "native": ""} for t in targets],
        "comprehension_questions": [],
    }


@pytest.fixture
async def lexicon(db_session):
    await load_gender_lexicon(
        db_session,
        rows=[
            GenderRow(lemma="Haus", pos="noun", gender="das"),
            GenderRow(lemma="Frau", pos="noun", gender="die"),
            GenderRow(lemma="Mann", pos="noun", gender="der"),
            # Trampa real del fallback de compuestos: "Kinder" termina en "Inder".
            GenderRow(lemma="Inder", pos="noun", gender="der"),
        ],
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_flags_impossible_article(db_session, lexicon):
    out = await gender_article_violations(db_session, _content("Ich sehe die Haus."), language="de")
    assert out == ["die Haus (oracle: das)"]


@pytest.mark.asyncio
async def test_declined_forms_not_flagged(db_session, lexicon):
    # "der Frau" = dativo femenino (grammatical); "dem Mann" = dativo masculino.
    out = await gender_article_violations(
        db_session,
        _content("Ich gebe der Frau einen Apfel.", "Ich helfe dem Mann.", "Das Haus ist alt."),
        language="de",
    )
    assert out == []


@pytest.mark.asyncio
async def test_inflected_plural_not_flagged(db_session, lexicon):
    # "die Kinder" NO debe resolverse vía sufijo "Inder" (der) — exact/ci only.
    out = await gender_article_violations(
        db_session, _content("Die Kinder spielen."), language="de"
    )
    assert out == []


@pytest.mark.asyncio
async def test_unknown_noun_skipped_and_non_de_empty(db_session, lexicon):
    assert (
        await gender_article_violations(
            db_session, _content("Die Zettelwirtschaft wächst."), language="de"
        )
        == []
    )
    assert await gender_article_violations(db_session, _content("die Haus"), language="es") == []


@pytest.mark.asyncio
async def test_relative_pronoun_not_flagged(db_session, lexicon):
    # "der" tras coma es pronombre relativo (der Mann, der ...), NO artículo de
    # Brot — la coma obligatoria de la cláusula relativa lo delata. Under-flag.
    await load_gender_lexicon(db_session, rows=[GenderRow(lemma="Brot", pos="noun", gender="das")])
    await db_session.commit()
    out = await gender_article_violations(
        db_session, _content("Der Mann, der Brot kauft, ist müde."), language="de"
    )
    assert out == []


@pytest.mark.asyncio
async def test_flags_after_clause_when_not_preceded_by_punct(db_session, lexicon):
    # Control positivo: el error dentro de la cláusula SÍ se flaggea cuando el
    # artículo no viene precedido de puntuación.
    out = await gender_article_violations(
        db_session, _content("Er sagt, dass die Haus brennt."), language="de"
    )
    assert out == ["die Haus (oracle: das)"]


@pytest.mark.asyncio
async def test_zero_plural_nouns_not_flagged(db_session, lexicon):
    # "Die Mädchen" es plural gramatical aunque el oráculo diga das (singular);
    # "der Fenster" es genitivo plural. Plural-cero → skip, under-flag by design.
    await load_gender_lexicon(
        db_session,
        rows=[
            GenderRow(lemma="Mädchen", pos="noun", gender="das"),
            GenderRow(lemma="Fenster", pos="noun", gender="das"),
        ],
    )
    await db_session.commit()
    out = await gender_article_violations(
        db_session,
        _content("Die Mädchen spielen.", "Ich mag die Farbe der Fenster."),
        language="de",
    )
    assert out == []


@pytest.mark.asyncio
async def test_das_with_zero_plural_suffix_still_checked(db_session, lexicon):
    # "das" nunca es artículo plural: "das Lehrer" (oracle: der) sigue siendo
    # un error probable y se flaggea.
    await load_gender_lexicon(
        db_session, rows=[GenderRow(lemma="Lehrer", pos="noun", gender="der")]
    )
    await db_session.commit()
    out = await gender_article_violations(
        db_session, _content("Ich sehe das Lehrer."), language="de"
    )
    assert out == ["das Lehrer (oracle: der)"]


@pytest.mark.asyncio
async def test_multiple_violations_reported_in_order(db_session, lexicon):
    out = await gender_article_violations(
        db_session, _content("Das Frau kocht.", "Der Haus brennt."), language="de"
    )
    assert out == ["Das Frau (oracle: die)", "Der Haus (oracle: das)"]


@pytest.mark.asyncio
async def test_draft_carries_gender_violations(db_session, lexicon):
    payload = {
        "title": "Die Haus",
        "sentences": [{"target": "Ich sehe die Haus.", "native": "Veo la casa.", "new_words": []}],
        "comprehension_questions": [],
        "target_words": [{"lemma": "Haus", "pos": "noun", "gender": "das", "translation": "casa"}],
    }
    draft = await generate_story_draft(
        db_session,
        _FakeLLM(payload),
        level=CEFRLevel.A1,
        target_language="de",
        native_language="es",
        learning_context=None,
        topic=None,
        model=None,
        target_lemmas=["Haus"],
        module_objective=None,
        avoid_lemmas=[],
    )
    assert draft.dropped_lemmas == []  # coverage OK: "Haus" aparece en el texto
    assert draft.gender_violations == ["die Haus (oracle: das)"]
