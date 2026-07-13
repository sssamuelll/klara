"""services.story_lint: flags ONLY provable gender-article errors (sub-flag by design)."""

import pytest

from klara.curriculum.gender_lex import GenderRow, load_gender_lexicon
from klara.services.story_lint import gender_article_violations


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
async def test_multiple_violations_reported_in_order(db_session, lexicon):
    out = await gender_article_violations(
        db_session, _content("Das Frau kocht.", "Der Haus brennt."), language="de"
    )
    assert out == ["Das Frau (oracle: die)", "Der Haus (oracle: das)"]
