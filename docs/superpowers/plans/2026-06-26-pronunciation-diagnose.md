# Pronunciation Diagnose (#42) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a corrective pronunciation tip — naming the failing sound and how to fix it — for the single worst mispronounced word, off Azure per-phoneme scores we already receive and discard.

**Architecture:** A new additive `POST /pronunciation/diagnose` endpoint (the existing `phonetic-hints` stays untouched as the stress-hint path and the fallback). Read-along scoring switches to the IPA phoneme alphabet so the tip prompt sees real symbols. A dedicated `pronunciation_diagnoses` table is both the LLM cache (skip the call on a seen key) and the analytics log (`hit_count` → most-failed phonemes per L1). The frontend computes the worst bad word, fires `/diagnose` fire-and-forget, and renders the tip under that word's stress hint.

**Tech Stack:** FastAPI · SQLAlchemy (async) · Alembic · Pydantic · Azure Speech SDK · React 18 + TypeScript + Vite · i18next.

## Global Constraints

- **Tip contract:** ≤25 words, in the user's `native_language`, concrete/actionable (mouth anatomy, rhythm, comparison to an L1 sound), never "try again". `String(400)` cap.
- **Best-effort everywhere:** any LLM/parse/transport failure degrades to no tip — the `au-to-BÚS` stress hint always stays. `/diagnose` never 500s the UI.
- **`phonetic-hints` is NOT modified** — it remains the always-on stress-hint path for every bad word and the structural fallback.
- **One corrective tip per recording:** the single worst bad word only (lowest word `accuracy_score`).
- **native_language is read server-side** from the authenticated user, never trusted from the request body.
- **Read-along scoring uses `phonemeAlphabet: "IPA"`** (mirrors `score_unscripted`). No response-shape change.
- **i18n parity:** every new key exists in all 6 locales (`es` source); `i18n:check` must pass.
- **Migration:** `20260626_0013_pronunciation_diagnoses`, `down_revision = "20260622_0012"`.
- **Backend commands run from `backend/` via `uv run`. Frontend commands run from `frontend/` via `npm run`.**

## File Structure

**Backend**
- Create `backend/src/klara/models/pronunciation_diagnosis.py` — the `PronunciationDiagnosis` model (cache + analytics row).
- Modify `backend/src/klara/models/__init__.py` — register the model.
- Create `backend/alembic/versions/20260626_0013_pronunciation_diagnoses.py` — the table migration.
- Modify `backend/tests/conftest.py` — add `pronunciation_diagnoses` to the truncate list.
- Modify `backend/src/klara/pronunciation/schemas.py` — `DiagnoseRequest`, `DiagnoseResponse`.
- Create `backend/src/klara/services/pronunciation_diagnose.py` — `generate_diagnosis(...)` (weakest-phoneme pick, cache lookup/upsert, LLM call).
- Modify `backend/src/klara/routers/pronunciation.py` — `POST /diagnose`.
- Modify `backend/src/klara/pronunciation/azure_client.py` — IPA config for `score_pronunciation`.
- Create `backend/tests/test_pronunciation_diagnose.py` — model, service, endpoint tests.
- Modify `backend/tests/test_pronunciation.py` — IPA config helper test.

**Frontend**
- Modify `frontend/src/api/types.ts` — `DiagnoseRequest`, `DiagnoseResponse`.
- Modify `frontend/src/api/client.ts` — `api.diagnose(...)`.
- Modify `frontend/src/lib/pronunciation.ts` — `worstBadWord(words)` helper.
- Modify `frontend/src/lib/useSentencePractice.ts` — worst-word selection, `/diagnose` fetch, `diagnosis` state.
- Modify `frontend/src/components/SentenceView.tsx` — focus the worst word, render the tip + skeleton.
- Modify `frontend/src/locales/{es,en,de,fr,pt,ja}/common.json` — the diagnosing/loading key.

---

### Task 1: `pronunciation_diagnoses` model + migration

**Files:**
- Create: `backend/src/klara/models/pronunciation_diagnosis.py`
- Modify: `backend/src/klara/models/__init__.py`
- Create: `backend/alembic/versions/20260626_0013_pronunciation_diagnoses.py`
- Modify: `backend/tests/conftest.py:74-80` (the TRUNCATE statement)
- Test: `backend/tests/test_pronunciation_diagnose.py`

**Interfaces:**
- Produces: `PronunciationDiagnosis` ORM model — columns `id, native_language, target_language, word, weakest_phoneme, phoneme_score, tip, hit_count, created_at, updated_at`; unique key `(native_language, target_language, word, weakest_phoneme)` named `uq_pron_diag_key`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_pronunciation_diagnose.py
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from klara.models.pronunciation_diagnosis import PronunciationDiagnosis


@pytest.mark.asyncio
async def test_insert_and_read_back(db_session):
    db_session.add(
        PronunciationDiagnosis(
            native_language="es",
            target_language="de",
            word="autobus",
            weakest_phoneme="uː",
            phoneme_score=38.0,
            tip="La ú es cerrada: redondea los labios.",
        )
    )
    await db_session.commit()
    row = (
        await db_session.execute(
            select(PronunciationDiagnosis).where(PronunciationDiagnosis.word == "autobus")
        )
    ).scalar_one()
    assert row.hit_count == 1
    assert row.weakest_phoneme == "uː"


@pytest.mark.asyncio
async def test_unique_key_blocks_duplicates(db_session):
    for _ in range(2):
        db_session.add(
            PronunciationDiagnosis(
                native_language="es", target_language="de", word="haus",
                weakest_phoneme="aʊ", phoneme_score=40.0, tip="x",
            )
        )
    with pytest.raises(IntegrityError):
        await db_session.commit()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_pronunciation_diagnose.py -v`
Expected: FAIL — `ModuleNotFoundError: klara.models.pronunciation_diagnosis` (and the table does not exist).

- [ ] **Step 3: Write the model**

```python
# backend/src/klara/models/pronunciation_diagnosis.py
"""LLM-authored corrective pronunciation tip for one (L1, target, word, weakest IPA phoneme).

Doubles as the cache (skip the LLM on a seen key) and the analytics log
(hit_count → which phonemes a given L1 fails most). Language-pair-keyed, not
per-user: a tip is a fact about a sound clash, not about a person.
"""

from __future__ import annotations

from sqlalchemy import Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from klara.models.base import Base, created_ts, updated_ts, uuid_pk


class PronunciationDiagnosis(Base):
    __tablename__ = "pronunciation_diagnoses"
    __table_args__ = (
        UniqueConstraint(
            "native_language", "target_language", "word", "weakest_phoneme",
            name="uq_pron_diag_key",
        ),
        Index("ix_pron_diag_phoneme", "native_language", "target_language", "weakest_phoneme"),
    )

    id: Mapped[uuid_pk]
    native_language: Mapped[str] = mapped_column(String(8), nullable=False)
    target_language: Mapped[str] = mapped_column(String(8), nullable=False)
    word: Mapped[str] = mapped_column(String(120), nullable=False)         # canonical lower-cased key
    weakest_phoneme: Mapped[str] = mapped_column(String(32), nullable=False)
    phoneme_score: Mapped[float] = mapped_column(Float, nullable=False)
    tip: Mapped[str] = mapped_column(String(400), nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[created_ts]
    updated_at: Mapped[updated_ts]
```

Register it in `backend/src/klara/models/__init__.py` (add the import next to the others and the name to `__all__`):

```python
from klara.models.pronunciation_diagnosis import PronunciationDiagnosis
```
```python
    "PronunciationDiagnosis",
```

- [ ] **Step 4: Write the migration**

```python
# backend/alembic/versions/20260626_0013_pronunciation_diagnoses.py
"""pronunciation_diagnoses cache + analytics table

Revision ID: 20260626_0013
Revises: 20260622_0012
Create Date: 2026-06-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260626_0013"
down_revision: str | None = "20260622_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pronunciation_diagnoses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("native_language", sa.String(8), nullable=False),
        sa.Column("target_language", sa.String(8), nullable=False),
        sa.Column("word", sa.String(120), nullable=False),
        sa.Column("weakest_phoneme", sa.String(32), nullable=False),
        sa.Column("phoneme_score", sa.Float(), nullable=False),
        sa.Column("tip", sa.String(400), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "native_language", "target_language", "word", "weakest_phoneme",
            name="uq_pron_diag_key",
        ),
    )
    op.create_index(
        "ix_pron_diag_phoneme",
        "pronunciation_diagnoses",
        ["native_language", "target_language", "weakest_phoneme"],
    )


def downgrade() -> None:
    op.drop_index("ix_pron_diag_phoneme", table_name="pronunciation_diagnoses")
    op.drop_table("pronunciation_diagnoses")
```

Add the table to the truncate list in `backend/tests/conftest.py` (the `TRUNCATE` string, after `gender_l1_notes,`):

```python
                "gender_attempts, gender_lexicon, gender_l1_notes, pronunciation_diagnoses, users "
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_pronunciation_diagnose.py -v`
Expected: PASS (both tests). The session-scoped `_prepare_database` fixture runs `alembic upgrade head`, creating the table.

- [ ] **Step 6: Verify the migration round-trips**

Run: `cd backend && uv run alembic downgrade base && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head`
Expected: no errors; `pronunciation_diagnoses` created/dropped/recreated cleanly.

- [ ] **Step 7: Commit**

```bash
git add backend/src/klara/models/pronunciation_diagnosis.py backend/src/klara/models/__init__.py backend/alembic/versions/20260626_0013_pronunciation_diagnoses.py backend/tests/conftest.py backend/tests/test_pronunciation_diagnose.py
git commit -m "feat(pronunciation): pronunciation_diagnoses cache+analytics table (#42)"
```

---

### Task 2: Diagnose schemas + `generate_diagnosis` service

**Files:**
- Modify: `backend/src/klara/pronunciation/schemas.py`
- Create: `backend/src/klara/services/pronunciation_diagnose.py`
- Test: `backend/tests/test_pronunciation_diagnose.py` (append)

**Interfaces:**
- Consumes: `PronunciationDiagnosis` (Task 1); `PhonemeScore` (existing, `pronunciation/schemas.py`); `_extract_json` (existing, `services/phonetic_hints.py`); `LLMClient`, `Message` (`klara.llm.base`).
- Produces:
  - `DiagnoseRequest{ language: str, word: str, phonemes: list[PhonemeScore] }`
  - `DiagnoseResponse{ tip: str = "", weakest_phoneme: str = "" }`
  - `async generate_diagnosis(llm: LLMClient, db: AsyncSession, *, word: str, phonemes: list[PhonemeScore], target_language: str, native_language: str) -> DiagnoseResponse`

- [ ] **Step 1: Write the failing tests**

```python
# append to backend/tests/test_pronunciation_diagnose.py
from sqlalchemy import func

from klara.llm.base import LLMResponse
from klara.pronunciation.schemas import PhonemeScore
from klara.services.pronunciation_diagnose import generate_diagnosis


class FakeLLM:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = 0
        self.last_messages = None

    async def complete(self, *, messages, model=None, max_tokens=1024, temperature=0.7, response_format=None):
        self.calls += 1
        self.last_messages = messages
        return LLMResponse(content=self.content, model="fake", provider="fake")

    async def stream(self, *, messages, model=None, max_tokens=1024, temperature=0.7):
        raise NotImplementedError


def _phonemes():
    return [PhonemeScore(phoneme="aʊ", accuracy_score=90.0), PhonemeScore(phoneme="uː", accuracy_score=38.0)]


@pytest.mark.asyncio
async def test_empty_phonemes_skips_llm(db_session):
    llm = FakeLLM('{"tip": "x"}')
    out = await generate_diagnosis(llm, db_session, word="Haus", phonemes=[], target_language="de", native_language="es")
    assert out.tip == "" and out.weakest_phoneme == ""
    assert llm.calls == 0


@pytest.mark.asyncio
async def test_cache_miss_calls_llm_and_inserts_row(db_session):
    llm = FakeLLM('{"tip": "La ú es cerrada: redondea los labios."}')
    out = await generate_diagnosis(llm, db_session, word="Autobus", phonemes=_phonemes(), target_language="de-DE", native_language="es")
    assert out.weakest_phoneme == "uː"
    assert "redondea" in out.tip
    assert llm.calls == 1
    count = (await db_session.execute(select(func.count()).select_from(PronunciationDiagnosis))).scalar()
    assert count == 1
    row = (await db_session.execute(select(PronunciationDiagnosis))).scalar_one()
    assert row.word == "autobus" and row.target_language == "de" and row.native_language == "es"


@pytest.mark.asyncio
async def test_cache_hit_skips_llm_and_bumps_hit_count(db_session):
    first = FakeLLM('{"tip": "tip uno"}')
    await generate_diagnosis(first, db_session, word="Autobus", phonemes=_phonemes(), target_language="de", native_language="es")
    second = FakeLLM('{"tip": "tip dos — should NOT be used"}')
    out = await generate_diagnosis(second, db_session, word="autobus", phonemes=_phonemes(), target_language="de", native_language="es")
    assert out.tip == "tip uno"          # cached value, not the new LLM content
    assert second.calls == 0
    row = (await db_session.execute(select(PronunciationDiagnosis))).scalar_one()
    assert row.hit_count == 2


@pytest.mark.asyncio
async def test_malformed_json_returns_empty_no_row(db_session):
    llm = FakeLLM("not json at all")
    out = await generate_diagnosis(llm, db_session, word="Haus", phonemes=_phonemes(), target_language="de", native_language="es")
    assert out.tip == ""
    count = (await db_session.execute(select(func.count()).select_from(PronunciationDiagnosis))).scalar()
    assert count == 0


@pytest.mark.asyncio
async def test_blank_tip_returns_empty_no_row(db_session):
    llm = FakeLLM('{"tip": "   "}')
    out = await generate_diagnosis(llm, db_session, word="Haus", phonemes=_phonemes(), target_language="de", native_language="es")
    assert out.tip == ""
    count = (await db_session.execute(select(func.count()).select_from(PronunciationDiagnosis))).scalar()
    assert count == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_pronunciation_diagnose.py -k "phonemes or cache or malformed or blank" -v`
Expected: FAIL — `cannot import name 'generate_diagnosis'` / `DiagnoseResponse`.

- [ ] **Step 3: Add the schemas**

Append to `backend/src/klara/pronunciation/schemas.py`:

```python
class DiagnoseRequest(BaseModel):
    language: str = Field(..., min_length=2, max_length=8)
    word: str = Field(..., min_length=1, max_length=120)
    phonemes: list[PhonemeScore] = Field(..., min_length=1)


class DiagnoseResponse(BaseModel):
    tip: str = ""
    weakest_phoneme: str = ""
```

- [ ] **Step 4: Write the service**

```python
# backend/src/klara/services/pronunciation_diagnose.py
"""LLM-backed corrective pronunciation tip for the single worst mispronounced word.

Clone of the phonetic_hints discipline (strict JSON, best-effort), plus a
cache/analytics row keyed by (native_language, target_language, word,
weakest IPA phoneme). On any failure the tip is empty and the caller keeps
showing the stress hint.
"""

from __future__ import annotations

import json

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from klara.i18n.languages import language_label
from klara.llm.base import LLMClient, Message
from klara.models.pronunciation_diagnosis import PronunciationDiagnosis
from klara.pronunciation.schemas import DiagnoseResponse, PhonemeScore
from klara.services.phonetic_hints import _extract_json

log = structlog.get_logger(__name__)

_SYSTEM_PROMPT = """You are a pronunciation coach. The learner's native language is {native_label}.
They mispronounced the {target_label} word «{word}»; the weakest sound was the IPA phoneme /{phoneme}/.

Write ONE corrective tip:
- ≤25 words, written in {native_label}.
- Concrete and physical: lips, tongue, jaw, airflow, rhythm — or a comparison to a {native_label} sound.
- Tell them what to DO. Never "try again", never abstract.

Return STRICT JSON only: {{"tip": "..."}}"""


def _short(lang: str) -> str:
    return lang.split("-")[0].lower()


async def generate_diagnosis(
    llm: LLMClient,
    db: AsyncSession,
    *,
    word: str,
    phonemes: list[PhonemeScore],
    target_language: str,
    native_language: str,
) -> DiagnoseResponse:
    if not phonemes:
        return DiagnoseResponse()
    weakest = min(phonemes, key=lambda p: p.accuracy_score)

    key_word = word.strip().lower()
    nl = _short(native_language)
    tl = _short(target_language)
    if not key_word:
        return DiagnoseResponse()

    existing = (
        await db.execute(
            select(PronunciationDiagnosis).where(
                PronunciationDiagnosis.native_language == nl,
                PronunciationDiagnosis.target_language == tl,
                PronunciationDiagnosis.word == key_word,
                PronunciationDiagnosis.weakest_phoneme == weakest.phoneme,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.hit_count += 1
        await db.commit()
        return DiagnoseResponse(tip=existing.tip, weakest_phoneme=existing.weakest_phoneme)

    system = _SYSTEM_PROMPT.format(
        native_label=language_label(nl),
        target_label=language_label(tl),
        word=word.strip(),
        phoneme=weakest.phoneme,
    )
    resp = await llm.complete(
        messages=[Message(role="system", content=system), Message(role="user", content="Give the tip.")],
        max_tokens=128,
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    try:
        payload = _extract_json(resp.content)
    except (ValueError, json.JSONDecodeError) as e:
        log.warning("diagnose.parse_failed", error=str(e), raw=resp.content[:300])
        return DiagnoseResponse()

    tip = payload.get("tip")
    if not isinstance(tip, str) or not tip.strip():
        return DiagnoseResponse()
    tip = tip.strip()[:400]

    db.add(
        PronunciationDiagnosis(
            native_language=nl, target_language=tl, word=key_word,
            weakest_phoneme=weakest.phoneme, phoneme_score=weakest.accuracy_score, tip=tip,
        )
    )
    await db.commit()
    return DiagnoseResponse(tip=tip, weakest_phoneme=weakest.phoneme)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_pronunciation_diagnose.py -v`
Expected: PASS (all tests, including Task 1's).

- [ ] **Step 6: Commit**

```bash
git add backend/src/klara/pronunciation/schemas.py backend/src/klara/services/pronunciation_diagnose.py backend/tests/test_pronunciation_diagnose.py
git commit -m "feat(pronunciation): generate_diagnosis service with cache (#42)"
```

---

### Task 3: `POST /pronunciation/diagnose` endpoint

**Files:**
- Modify: `backend/src/klara/routers/pronunciation.py`
- Test: `backend/tests/test_pronunciation_diagnose.py` (append)

**Interfaces:**
- Consumes: `generate_diagnosis` (Task 2); `DiagnoseRequest`/`DiagnoseResponse` (Task 2); `CurrentUser`, `ChatLLM`, `DBSession` (`klara.dependencies`).
- Produces: `POST /api/v1/pronunciation/diagnose` → `DiagnoseResponse`. Reads `user.native_language`; best-effort (returns empty `DiagnoseResponse` on any service exception).

- [ ] **Step 1: Write the failing tests**

```python
# append to backend/tests/test_pronunciation_diagnose.py — endpoint tests
from tests.test_pronunciation import _register_and_login   # reuse the auth helper


@pytest.mark.asyncio
async def test_diagnose_requires_auth(client, app_settings):
    r = await client.post(
        "/api/v1/pronunciation/diagnose",
        json={"language": "de", "word": "Haus", "phonemes": [{"phoneme": "aʊ", "accuracy_score": 40.0}]},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_diagnose_uses_user_native_language(client, app_settings, seed_invite, monkeypatch):
    cookie = await _register_and_login(client, app_settings, seed_invite)
    captured = {}

    async def fake_generate(llm, db, *, word, phonemes, target_language, native_language):
        from klara.pronunciation.schemas import DiagnoseResponse
        captured["native_language"] = native_language
        captured["word"] = word
        return DiagnoseResponse(tip="redondea los labios", weakest_phoneme="uː")

    monkeypatch.setattr("klara.routers.pronunciation.generate_diagnosis", fake_generate)

    r = await client.post(
        "/api/v1/pronunciation/diagnose",
        headers={"Cookie": cookie},
        json={"language": "de", "word": "Autobus",
              "phonemes": [{"phoneme": "uː", "accuracy_score": 38.0}],
              "native_language": "INVALID-CLIENT-VALUE"},   # must be ignored
    )
    assert r.status_code == 200, r.text
    assert r.json()["tip"] == "redondea los labios"
    assert captured["native_language"] == "es"   # from the seeded user, not the body


@pytest.mark.asyncio
async def test_diagnose_service_error_is_best_effort(client, app_settings, seed_invite, monkeypatch):
    cookie = await _register_and_login(client, app_settings, seed_invite)

    async def boom(*a, **k):
        raise RuntimeError("llm down")

    monkeypatch.setattr("klara.routers.pronunciation.generate_diagnosis", boom)

    r = await client.post(
        "/api/v1/pronunciation/diagnose",
        headers={"Cookie": cookie},
        json={"language": "de", "word": "Haus", "phonemes": [{"phoneme": "aʊ", "accuracy_score": 40.0}]},
    )
    assert r.status_code == 200
    assert r.json() == {"tip": "", "weakest_phoneme": ""}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_pronunciation_diagnose.py -k diagnose_ -v`
Expected: FAIL — 404 (route not registered) on the authed tests.

- [ ] **Step 3: Add the endpoint**

In `backend/src/klara/routers/pronunciation.py`, extend the imports and add the route. Update the schema import block and the dependencies import:

```python
from klara.dependencies import ChatLLM, CurrentUser, DBSession, LocaleDep, SettingsDep
```
```python
from klara.pronunciation.schemas import (
    DiagnoseRequest,
    DiagnoseResponse,
    PhoneticHintsRequest,
    PhoneticHintsResponse,
    ScoreResponse,
)
from klara.services.phonetic_hints import generate_phonetic_hints
from klara.services.pronunciation_diagnose import generate_diagnosis
```

Append after the `phonetic_hints` route:

```python
@router.post("/diagnose", response_model=DiagnoseResponse)
async def diagnose(
    user: CurrentUser,
    llm: ChatLLM,
    db: DBSession,
    payload: DiagnoseRequest,
) -> DiagnoseResponse:
    """Corrective tip for the single worst mispronounced word.

    Best-effort: any failure returns an empty tip so the UI keeps the
    stress hint. native_language comes from the authenticated user, never
    the request body.
    """
    try:
        return await generate_diagnosis(
            llm,
            db,
            word=payload.word,
            phonemes=payload.phonemes,
            target_language=payload.language,
            native_language=user.native_language,
        )
    except Exception:
        return DiagnoseResponse()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_pronunciation_diagnose.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add backend/src/klara/routers/pronunciation.py backend/tests/test_pronunciation_diagnose.py
git commit -m "feat(pronunciation): POST /diagnose endpoint (#42)"
```

---

### Task 4: Read-along scoring switches to IPA

**Files:**
- Modify: `backend/src/klara/pronunciation/azure_client.py:61-100`
- Test: `backend/tests/test_pronunciation.py` (append)

**Interfaces:**
- Produces: `_read_along_config_json(reference_text: str) -> str` — the `PronunciationAssessmentConfig` json_string for read-along, with `phonemeAlphabet: "IPA"`.

- [ ] **Step 1: Write the failing test**

```python
# append to backend/tests/test_pronunciation.py
import json as _json


def test_read_along_config_is_ipa():
    from klara.pronunciation.azure_client import _read_along_config_json

    cfg = _json.loads(_read_along_config_json("Ich fahre mit dem Autobus."))
    assert cfg["phonemeAlphabet"] == "IPA"
    assert cfg["granularity"] == "Phoneme"
    assert cfg["gradingSystem"] == "HundredMark"
    assert cfg["enableMiscue"] is False
    # reference text is sanitized (trailing period stripped) but words survive
    assert "Autobus" in cfg["referenceText"]
    assert not cfg["referenceText"].endswith(".")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_pronunciation.py::test_read_along_config_is_ipa -v`
Expected: FAIL — `cannot import name '_read_along_config_json'`.

- [ ] **Step 3: Extract the config helper and use IPA**

In `backend/src/klara/pronunciation/azure_client.py`, add the helper near `_sanitize_reference` and replace the inline `PronunciationAssessmentConfig(...)` in `score_pronunciation` with the json_string form:

```python
def _read_along_config_json(reference_text: str) -> str:
    """Read-along assessment config as a json_string so phonemeAlphabet can be
    set to IPA (the SDK constructor has no kwarg for it). IPA keeps the
    read-along phonemes consistent with score_unscripted and lets the
    diagnose prompt reason over real symbols. enable_miscue stays False: in
    read-along the learner is reading the reference, so miscue detection mostly
    mis-flags accent variation and tanks the score."""
    return json.dumps(
        {
            "referenceText": _sanitize_reference(reference_text),
            "gradingSystem": "HundredMark",
            "granularity": "Phoneme",
            "phonemeAlphabet": "IPA",
            "enableMiscue": False,
        }
    )
```

Then in `score_pronunciation`, replace the `sanitized_reference = ...` + `pronunciation_config = speechsdk.PronunciationAssessmentConfig(reference_text=..., grading_system=..., granularity=..., enable_miscue=False)` block with:

```python
    sanitized_reference = _sanitize_reference(reference_text)

    pronunciation_config = speechsdk.PronunciationAssessmentConfig(
        json_string=_read_along_config_json(reference_text)
    )
```

(The `PhraseListGrammar` block below it that iterates `sanitized_reference.split()` stays unchanged.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_pronunciation.py -v`
Expected: PASS — the new IPA test plus all existing score tests (the patched-Azure tests are unaffected; the helper is pure).

- [ ] **Step 5: Commit**

```bash
git add backend/src/klara/pronunciation/azure_client.py backend/tests/test_pronunciation.py
git commit -m "feat(pronunciation): read-along scoring uses IPA phoneme alphabet (#42)"
```

---

### Task 5: Frontend API types + client method

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts:262-272`

**Interfaces:**
- Consumes: `PhonemeScore` (existing, `types.ts:134`).
- Produces: `DiagnoseRequest`, `DiagnoseResponse` types; `api.diagnose(word, phonemes, language) => Promise<DiagnoseResponse>`.

- [ ] **Step 1: Add the types**

Append to `frontend/src/api/types.ts`:

```typescript
export interface DiagnoseRequest {
  language: string;
  word: string;
  phonemes: PhonemeScore[];
}

export interface DiagnoseResponse {
  tip: string;
  weakest_phoneme: string;
}
```

- [ ] **Step 2: Add the client method**

Add the import to the type import block in `frontend/src/api/client.ts` (next to `PhoneticHintsResponse`):

```typescript
  DiagnoseResponse,
```

Add the method next to `getPhoneticHints`:

```typescript
  /**
   * Corrective tip for the single worst mispronounced word. Best-effort: the
   * endpoint returns `{tip: "", weakest_phoneme: ""}` on any failure, so the
   * caller keeps showing the stress hint.
   */
  diagnose: (word: string, phonemes: PhonemeScore[], language: string) =>
    request<DiagnoseResponse>("/pronunciation/diagnose", {
      method: "POST",
      body: JSON.stringify({ word, phonemes, language }),
    }),
```

Ensure `PhonemeScore` is imported in `client.ts` (add to the type import block if absent).

- [ ] **Step 3: Verify types compile**

Run: `cd frontend && npm run typecheck`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts
git commit -m "feat(pronunciation): frontend diagnose api types + client (#42)"
```

---

### Task 6: Hook — worst-word selection + diagnose fetch + state

**Files:**
- Modify: `frontend/src/lib/pronunciation.ts` (add `worstBadWord`)
- Modify: `frontend/src/lib/useSentencePractice.ts`

**Interfaces:**
- Consumes: `api.diagnose` (Task 5); `WordScore` (`types.ts`); the score response `resp.words` already in scope in `handleScore`.
- Produces:
  - `worstBadWord(words: WordScore[]): WordScore | null` in `pronunciation.ts` — lowest-`accuracy_score` word whose band is `bad`, else `null`.
  - Hook state `diagnosisBySentence: Record<number, { word: string; tip: string }>` and a flat `diagnosis?: { word: string; tip: string }` on the returned object for the current sentence.

- [ ] **Step 1: Add the `worstBadWord` helper**

In `frontend/src/lib/pronunciation.ts`, reuse the existing band threshold (the same cutoff `bandsByTokenIndex` uses for `bad`) and add:

```typescript
/** The lowest-scoring word that bands as "bad", or null if none is bad.
 *  Used to target the single corrective diagnose tip. */
export function worstBadWord(words: WordScore[]): WordScore | null {
  let worst: WordScore | null = null;
  for (const w of words) {
    if (scoreBand(w.accuracy_score) !== "bad") continue;
    if (worst === null || w.accuracy_score < worst.accuracy_score) worst = w;
  }
  return worst;
}
```

If a single-score band helper does not already exist in `pronunciation.ts`, add it from the same thresholds `bandsByTokenIndex` uses and have both call it:

```typescript
export function scoreBand(accuracy: number): ScoreBand {
  if (accuracy >= 80) return "good";
  if (accuracy >= 60) return "ok";
  return "bad";
}
```

(Match the exact cutoffs already in `bandsByTokenIndex` — read them there and keep one source of truth; the 80/60 values above are the expected defaults, confirm against the file.)

- [ ] **Step 2: Add diagnose state + fetch to the hook**

In `frontend/src/lib/useSentencePractice.ts`:

Add state next to `phoneticHintsBySentence`:

```typescript
  const [diagnosisBySentence, setDiagnosisBySentence] = useState<
    Record<number, { word: string; tip: string }>
  >({});
```

Clear it in the same `useEffect` that clears `phoneticHintsBySentence` on sentence change, and in the reset path that calls `setPhoneticHintsBySentence({})`:

```typescript
    setDiagnosisBySentence((s) => {
      if (!(currentIndex in s)) return s;
      const next = { ...s };
      delete next[currentIndex];
      return next;
    });
```
```typescript
    setDiagnosisBySentence({});
```

Add a fetcher next to `fetchAndStoreHints`:

```typescript
  const fetchAndStoreDiagnosis = useCallback(
    async (idx: number, words: WordScore[], language: string) => {
      const worst = worstBadWord(words);
      if (!worst) return;
      try {
        const resp = await api.diagnose(worst.word, worst.phonemes, language);
        if (!resp.tip) return;
        setDiagnosisBySentence((s) => ({ ...s, [idx]: { word: worst.word, tip: resp.tip } }));
      } catch {
        // best-effort: no tip, the stress hint stays.
      }
    },
    [],
  );
```

Fire it right after the existing `fetchAndStoreHints` call in `handleScore` (it has `resp.words` in scope):

```typescript
      void fetchAndStoreDiagnosis(idxAtStart, resp.words, targetLanguage);
```

Add `fetchAndStoreDiagnosis` to that `useCallback`'s dependency array (alongside `fetchAndStoreHints`).

Expose the current-sentence value next to `phoneticHints`:

```typescript
  const diagnosis = diagnosisBySentence[currentIndex];
```
```typescript
    diagnosis,
```

Import `worstBadWord` and `WordScore`:

```typescript
import { worstBadWord } from "./pronunciation";
import type { WordScore } from "../api/types";
```

- [ ] **Step 3: Verify types compile**

Run: `cd frontend && npm run typecheck`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/pronunciation.ts frontend/src/lib/useSentencePractice.ts
git commit -m "feat(pronunciation): hook fetches worst-word diagnose (#42)"
```

---

### Task 7: SentenceView — focus the worst word, render tip + skeleton + i18n

**Files:**
- Modify: `frontend/src/components/SentenceView.tsx`
- Modify: `frontend/src/locales/{es,en,de,fr,pt,ja}/common.json`

**Interfaces:**
- Consumes: `diagnosis?: { word: string; tip: string }` (Task 6); existing `feedback`, `phoneticHints`, `tokens`.

- [ ] **Step 1: Accept the `diagnosis` prop**

Add to the `SentenceViewProps` interface (next to `phoneticHints?`):

```typescript
  diagnosis?: { word: string; tip: string };
```

Add `diagnosis,` to the destructured props in the component signature (next to `phoneticHints,`).

- [ ] **Step 2: Focus the worst word and surface the tip**

Replace the `badWordTip` memo (`SentenceView.tsx:291-305`) so the focus word is the diagnosed worst word when present (falling back to the first bad word — the simulated-fallback path has no diagnosis), and carry the corrective tip:

```typescript
  // ---- Bad-word tip: stress hint + optional corrective diagnose ------------
  const badWordTip = useMemo(() => {
    if (!feedback) return null;
    // Focus the diagnosed worst word when we have it; else the first bad word.
    let focus: string | null = diagnosis?.word ?? null;
    if (focus === null) {
      for (let i = 0; i < tokens.length; i++) {
        const tok = tokens[i];
        if (tok.type === "word" && feedback[i] === "bad") {
          focus = tok.text;
          break;
        }
      }
    }
    if (focus === null) return null;
    const tip = diagnosis && diagnosis.word === focus ? diagnosis.tip : null;
    return { word: focus, hint: phoneticHints?.[focus] ?? null, tip };
  }, [feedback, phoneticHints, tokens, diagnosis]);
```

Determine whether the corrective tip is still loading (a bad word exists but no diagnosis yet) for the skeleton:

```typescript
  const diagnosing = useMemo(
    () => Boolean(badWordTip && badWordTip.hint && !badWordTip.tip && !diagnosis),
    [badWordTip, diagnosis],
  );
```

- [ ] **Step 3: Render the corrective tip / skeleton**

In the feedback block (`SentenceView.tsx:528-542`), after the existing `<em>{badWordTip.hint}</em>.` stress-hint render, append the corrective tip line:

```tsx
                  {badWordTip.tip && (
                    <span className="k-diagnose-tip"> {badWordTip.tip}</span>
                  )}
                  {diagnosing && (
                    <span className="k-diagnose-tip k-diagnose-tip--loading">
                      {" "}
                      {t("story.sentence.feedback.diagnosing")}
                    </span>
                  )}
```

- [ ] **Step 4: Add the i18n key to all 6 locales**

Add `diagnosing` under `story.sentence.feedback` in each `frontend/src/locales/<lang>/common.json` (sibling of the existing `tipPrefix`). Source `es`; the others are translations (run through solace-wren before merge, but parity is required now):

- `es`: `"diagnosing": "analizando el sonido…"`
- `en`: `"diagnosing": "analyzing the sound…"`
- `de`: `"diagnosing": "Laut wird analysiert…"`
- `fr`: `"diagnosing": "analyse du son…"`
- `pt`: `"diagnosing": "analisando o som…"`
- `ja`: `"diagnosing": "音を分析中…"`

- [ ] **Step 5: Pass `diagnosis` from the consumers into SentenceView**

`SentenceView` is rendered by `Story.tsx` and `Practice.tsx` from the hook's flat return. Add `diagnosis={pron.diagnosis}` (or the matching destructured name) wherever `phoneticHints={...}` is already passed in both files.

- [ ] **Step 6: Verify**

Run: `cd frontend && npm run typecheck && npm run i18n:check && npm run build`
Expected: all pass — types clean, locale parity holds, production build succeeds.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/SentenceView.tsx frontend/src/routes/Story.tsx frontend/src/routes/Practice.tsx frontend/src/locales
git commit -m "feat(pronunciation): render corrective diagnose tip in SentenceView (#42)"
```

---

## Self-Review

**1. Spec coverage**
- New additive `/diagnose` (D1) → Task 3. ✓
- Worst word only (D2) → `worstBadWord` Task 6 + focus Task 7. ✓
- Additive UX, stress hint kept (D3) → Task 7 keeps `phoneticHints` render, appends tip. ✓
- Read-along → IPA (D4) → Task 4. ✓
- Responsibility split: frontend picks worst word, backend reads native_language + picks weakest phoneme (D5) → Task 6 (worst word) + Task 2/3 (native_language from user, `min()` weakest). ✓
- Cache + analytics table (D6) → Task 1 (table) + Task 2 (lookup/insert/hit_count). ✓
- Tip contract ≤25 words / L1 / actionable (D7) → Task 2 prompt + 400-char cap. ✓
- Level calibration OUT (D8) → not implemented. ✓
- Error degradation cascade → Task 2 (empty on failure, no row), Task 3 (try/except → empty), Task 6 (catch → no tip). ✓
- Testing per spec → model/service/endpoint Tasks 1-3, IPA Task 4, frontend typecheck/build/i18n Tasks 5-7. ✓

**2. Placeholder scan:** No TBD/TODO/"handle errors" — every step shows the code. The one "confirm against the file" note (Task 6 band cutoffs) is a real instruction to reuse existing thresholds, not a placeholder; the fallback values are given.

**3. Type consistency:** `DiagnoseResponse{tip, weakest_phoneme}` identical across schema (Task 2), endpoint (Task 3), TS type (Task 5). `generate_diagnosis` signature identical in Task 2 (def), Task 3 (call), and the Task 3 fake. `worstBadWord(words) -> WordScore | null` consistent Task 6 def → hook use. `diagnosis: {word, tip}` consistent Task 6 (hook) → Task 7 (prop). Endpoint path `/pronunciation/diagnose` consistent across Task 3 and Task 5.
