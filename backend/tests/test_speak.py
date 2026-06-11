"""Tests for /api/v1/speak — turn pipeline and the Practice hand-off.

Azure + LLM are monkeypatched at the router's import site (same convention as
test_pronunciation.py). The one test that MUST stay green forever:
finish → the struggled word appears in GET /practice/queue — that hand-off is
the reason Speak exists in the MVP.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select

from klara.models import StudySession, UserCard, VocabItem
from klara.pronunciation.schemas import (
    PhonemeScore,
    PronunciationScores,
    ScoreResponse,
    WordScore,
)
from klara.services.speak_chat import SpeakReply


async def _register_and_login(client, app_settings, seed_invite) -> str:
    app_settings(INITIAL_OWNER_EMAIL="", AZURE_SPEECH_KEY="dummy-key")
    token = await seed_invite(email=None)
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "speak@example.com",
            "password": "hunter2hunter2",
            "invite_token": token,
        },
    )
    assert r.status_code == 201, r.text
    r2 = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": "speak@example.com", "password": "hunter2hunter2"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r2.status_code == 204
    return r2.headers["set-cookie"].split(";")[0]


def _score_response(words: list[WordScore] | None = None, text: str | None = None) -> ScoreResponse:
    if words is None:
        words = [
            WordScore(
                word="fünf",
                accuracy_score=55.0,
                error_type="None",
                phonemes=[
                    PhonemeScore(phoneme="f", accuracy_score=90.0),
                    PhonemeScore(phoneme="ʏ", accuracy_score=40.0),
                    PhonemeScore(phoneme="n", accuracy_score=88.0),
                    PhonemeScore(phoneme="f", accuracy_score=91.0),
                ],
            ),
            WordScore(
                word="Minuten",
                accuracy_score=92.0,
                error_type="None",
                phonemes=[PhonemeScore(phoneme="m", accuracy_score=95.0)],
            ),
        ]
    return ScoreResponse(
        recognized_text=text if text is not None else " ".join(w.word for w in words),
        reference_text="",
        language="de-DE",
        scores=PronunciationScores(
            accuracy=80.0, fluency=75.0, completeness=100.0, pronunciation=78.0
        ),
        words=words,
    )


@pytest.fixture
def patched_turn(monkeypatch, tmp_path: Path):
    """Stub transcode + Azure unscripted + LLM. Tests override pieces."""

    def fake_transcode(audio_bytes: bytes, *, sample_rate: int = 16_000) -> Path:
        out = tmp_path / "fake.wav"
        out.write_bytes(b"RIFFfake")
        return out

    monkeypatch.setattr("klara.routers.speak.transcode_to_wav", fake_transcode)

    def fake_score(wav_path, language, *, azure_key, azure_region):
        return _score_response(), 0.92

    monkeypatch.setattr("klara.routers.speak.score_unscripted", fake_score)

    captured: dict = {}

    async def fake_reply(llm, **kwargs):
        captured.update(kwargs)
        return SpeakReply(
            reply_target="Fünf Minuten — nicht schlecht. War die Tür schwer zu finden?",
            reply_native="Cinco minutos, no está mal. ¿Costó encontrar la puerta?",
            target_word_gloss="cinco",
            target_word_sentence="Ich musste fünf Minuten warten.",
        )

    monkeypatch.setattr("klara.routers.speak.generate_reply", fake_reply)
    return captured


def _turn_request(cookie: str, **extra):
    data = {"language": "de", "focus_sound": "ü", **extra}
    return {
        "headers": {"Cookie": cookie},
        "data": data,
        "files": {"audio": ("a.webm", b"\x00\x01\x02\x03", "audio/webm")},
    }


# ---- /speak/turn -----------------------------------------------------------


@pytest.mark.asyncio
async def test_turn_requires_auth(client, app_settings):
    app_settings(AZURE_SPEECH_KEY="dummy-key")
    r = await client.post(
        "/api/v1/speak/turn",
        data={"language": "de"},
        files={"audio": ("a.webm", b"\x00", "audio/webm")},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_turn_503_when_azure_unconfigured(client, app_settings, seed_invite):
    cookie = await _register_and_login(client, app_settings, seed_invite)
    app_settings(AZURE_SPEECH_KEY="")
    r = await client.post("/api/v1/speak/turn", **_turn_request(cookie))
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_turn_400_unsupported_language(client, app_settings, seed_invite):
    cookie = await _register_and_login(client, app_settings, seed_invite)
    r = await client.post("/api/v1/speak/turn", **_turn_request(cookie, language="fr"))
    assert r.status_code == 400
    assert "alem" in r.json()["detail"].lower() or "german" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_turn_happy_path(client, app_settings, seed_invite, patched_turn):
    cookie = await _register_and_login(client, app_settings, seed_invite)
    r = await client.post(
        "/api/v1/speak/turn",
        **_turn_request(cookie, history='[{"who":"klara","text":"Wie war es?"}]'),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["noSpeech"] is False
    assert body["recognizedText"] == "fünf Minuten"
    assert [tk["s"] for tk in body["tokens"]] == ["ok", "good"]
    assert [tk["focus"] for tk in body["tokens"]] == [True, False]
    assert body["focusHit"] is True
    assert body["focusClear"] is False
    assert body["target"]["word"] == "fünf"
    assert body["target"]["shouldIpa"] == "/fʏnf/"
    assert body["target"]["gloss"] == "cinco"
    assert body["target"]["modelSentence"] == "Ich musste fünf Minuten warten."
    assert body["reply"]["target"].startswith("Fünf Minuten")
    # History reached the LLM service
    assert patched_turn["history"] == [{"who": "klara", "text": "Wie war es?"}]


@pytest.mark.asyncio
async def test_turn_passes_retry_word_to_llm(client, app_settings, seed_invite, patched_turn):
    cookie = await _register_and_login(client, app_settings, seed_invite)
    r = await client.post("/api/v1/speak/turn", **_turn_request(cookie, retry_word="fünf"))
    assert r.status_code == 200
    assert patched_turn["retry_word"] == "fünf"


@pytest.mark.asyncio
async def test_turn_no_speech_when_azure_recoverable(
    client, app_settings, seed_invite, patched_turn, monkeypatch
):
    from klara.pronunciation.azure_client import AzureSpeechError

    cookie = await _register_and_login(client, app_settings, seed_invite)

    def raise_no_match(wav_path, language, *, azure_key, azure_region):
        raise AzureSpeechError("No speech", recoverable=True)

    monkeypatch.setattr("klara.routers.speak.score_unscripted", raise_no_match)
    r = await client.post("/api/v1/speak/turn", **_turn_request(cookie))
    assert r.status_code == 200
    body = r.json()
    assert body["noSpeech"] is True
    assert body["reply"] is None
    assert body["tokens"] == []


@pytest.mark.asyncio
async def test_turn_no_speech_when_recognition_empty(
    client, app_settings, seed_invite, patched_turn, monkeypatch
):
    """Azure can return RecognizedSpeech with empty text (a breath) — B4."""
    cookie = await _register_and_login(client, app_settings, seed_invite)

    def empty_score(wav_path, language, *, azure_key, azure_region):
        return _score_response(words=[], text="  "), 0.9

    monkeypatch.setattr("klara.routers.speak.score_unscripted", empty_score)
    r = await client.post("/api/v1/speak/turn", **_turn_request(cookie))
    assert r.status_code == 200
    assert r.json()["noSpeech"] is True


@pytest.mark.asyncio
async def test_turn_low_confidence_skips_conversation(
    client, app_settings, seed_invite, patched_turn, monkeypatch
):
    cookie = await _register_and_login(client, app_settings, seed_invite)

    def shaky_score(wav_path, language, *, azure_key, azure_region):
        return _score_response(), 0.31

    monkeypatch.setattr("klara.routers.speak.score_unscripted", shaky_score)
    r = await client.post("/api/v1/speak/turn", **_turn_request(cookie))
    assert r.status_code == 200
    body = r.json()
    assert body["lowConfidence"] is True
    assert body["recognizedText"] == "fünf Minuten"
    assert body["reply"] is None
    assert body["target"] is None


@pytest.mark.asyncio
async def test_turn_llm_failure_keeps_assessment(
    client, app_settings, seed_invite, patched_turn, monkeypatch
):
    """The scored turn must survive an LLM hiccup (spec review F14)."""
    cookie = await _register_and_login(client, app_settings, seed_invite)

    async def no_reply(llm, **kwargs):
        return None

    monkeypatch.setattr("klara.routers.speak.generate_reply", no_reply)
    r = await client.post("/api/v1/speak/turn", **_turn_request(cookie))
    assert r.status_code == 200
    body = r.json()
    assert body["reply"] is None
    assert body["recognizedText"] == "fünf Minuten"
    assert body["target"]["word"] == "fünf"
    assert body["target"]["gloss"] is None
    assert body["target"]["modelSentence"] is None


@pytest.mark.asyncio
async def test_turn_502_when_azure_fatal(
    client, app_settings, seed_invite, patched_turn, monkeypatch
):
    from klara.pronunciation.azure_client import AzureSpeechError

    cookie = await _register_and_login(client, app_settings, seed_invite)

    def raise_fatal(wav_path, language, *, azure_key, azure_region):
        raise AzureSpeechError("Quota exceeded", recoverable=False)

    monkeypatch.setattr("klara.routers.speak.score_unscripted", raise_fatal)
    r = await client.post("/api/v1/speak/turn", **_turn_request(cookie))
    assert r.status_code == 502


def test_result_to_response_missing_assessment_is_recoverable():
    """RecognizedSpeech with no PronunciationAssessment/Words block in the
    result JSON (a breath) must surface as a recoverable no-speech, not as an
    AttributeError-500 from inside the SDK's attribute-less result object."""
    import azure.cognitiveservices.speech as speechsdk

    from klara.pronunciation.azure_client import AzureSpeechError, _result_to_response

    class StubResult:
        reason = speechsdk.ResultReason.RecognizedSpeech
        text = ""

    with pytest.raises(AzureSpeechError) as excinfo:
        _result_to_response(StubResult(), reference_text="", language="de-DE")
    assert excinfo.value.recoverable is True


# ---- /speak/finish ----------------------------------------------------------

# vocab_items is deliberately NOT truncated between tests (shared corpus);
# clean this module's lemmas so re-runs and cross-test leftovers can't skew
# the assertions.
_TEST_LEMMAS = ["fünf", "tür", "bürgeramt"]


@pytest_asyncio.fixture
async def clean_vocab(db_session):
    await db_session.execute(delete(VocabItem).where(func.lower(VocabItem.lemma).in_(_TEST_LEMMAS)))
    await db_session.commit()
    yield


def _vocab_by_lemma(lemma: str):
    return select(VocabItem).where(func.lower(VocabItem.lemma) == lemma.lower())


def _finish_payload(**overrides):
    payload = {
        "language": "de",
        "focusSound": "ü",
        "clearCount": 5,
        "totalCount": 7,
        "durationSeconds": 240,
        "words": [
            {
                "word": "fünf",
                "gloss": "cinco",
                "modelSentence": "Ich musste fünf Minuten warten.",
            }
        ],
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_finish_closes_circle_with_practice_queue(
    client, app_settings, seed_invite, db_session, clean_vocab
):
    """THE critical integration test: a struggled Speak word must surface in
    the Practice queue as a review item — that hand-off is Speak's purpose."""
    cookie = await _register_and_login(client, app_settings, seed_invite)
    r = await client.post(
        "/api/v1/speak/finish", headers={"Cookie": cookie}, json=_finish_payload()
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"added": 1, "skipped": 0}

    q = await client.get("/api/v1/practice/queue", headers={"Cookie": cookie})
    assert q.status_code == 200, q.text
    items = q.json()["items"]
    focus_words = [it["focusText"] for it in items]
    assert "fünf" in focus_words
    item = next(it for it in items if it["focusText"] == "fünf")
    assert item["reason"] == "review"

    # Session row persisted with the wins payload
    session = (await db_session.execute(select(StudySession))).scalar_one()
    assert session.session_type.value == "chat"
    assert session.wins["focus_sound"] == "ü"
    assert session.wins["clear_count"] == 5
    assert session.ended_at is not None


@pytest.mark.asyncio
async def test_finish_skips_word_without_model_sentence(
    client, app_settings, seed_invite, db_session, clean_vocab
):
    """No model sentence → the practice queue would silently drop the card;
    don't create dead rows that pretend the hand-off worked (F1)."""
    cookie = await _register_and_login(client, app_settings, seed_invite)
    payload = _finish_payload(
        words=[{"word": "Bürgeramt", "gloss": "oficina", "modelSentence": None}]
    )
    r = await client.post("/api/v1/speak/finish", headers={"Cookie": cookie}, json=payload)
    assert r.status_code == 200
    assert r.json() == {"added": 0, "skipped": 1}
    leftover = (await db_session.execute(_vocab_by_lemma("Bürgeramt"))).scalars().all()
    assert leftover == []


@pytest.mark.asyncio
async def test_finish_never_overwrites_existing_vocab(
    client, app_settings, seed_invite, db_session, clean_vocab
):
    """vocab_items is global — client-supplied content must not clobber what
    other users' practice queues read (spec review F2)."""
    cookie = await _register_and_login(client, app_settings, seed_invite)
    db_session.add(
        VocabItem(
            lemma="Tür",
            language="de",
            example_target="Die Tür ist offen.",
            translations={"es": "puerta"},
        )
    )
    await db_session.commit()

    payload = _finish_payload(
        words=[{"word": "tür", "gloss": "portón", "modelSentence": "Neue Tür hier."}]
    )
    r = await client.post("/api/v1/speak/finish", headers={"Cookie": cookie}, json=payload)
    assert r.status_code == 200
    assert r.json() == {"added": 1, "skipped": 0}

    items = (await db_session.execute(_vocab_by_lemma("Tür"))).scalars().all()
    assert len(items) == 1  # matched case-insensitively, no duplicate row
    vocab = items[0]
    assert vocab.example_target == "Die Tür ist offen."  # NOT overwritten
    assert vocab.translations["es"] == "puerta"  # NOT overwritten
    card = (await db_session.execute(select(UserCard))).scalar_one()
    assert card.vocab_item_id == vocab.id


@pytest.mark.asyncio
async def test_finish_fills_only_empty_fields(
    client, app_settings, seed_invite, db_session, clean_vocab
):
    cookie = await _register_and_login(client, app_settings, seed_invite)
    db_session.add(VocabItem(lemma="fünf", language="de", translations={}))
    await db_session.commit()

    r = await client.post(
        "/api/v1/speak/finish", headers={"Cookie": cookie}, json=_finish_payload()
    )
    assert r.status_code == 200
    vocab = (await db_session.execute(_vocab_by_lemma("fünf"))).scalar_one()
    assert vocab.example_target == "Ich musste fünf Minuten warten."  # filled
    assert vocab.translations["es"] == "cinco"  # filled


@pytest.mark.asyncio
async def test_finish_400_on_language_mismatch(client, app_settings, seed_invite):
    cookie = await _register_and_login(client, app_settings, seed_invite)
    r = await client.post(
        "/api/v1/speak/finish",
        headers={"Cookie": cookie},
        json=_finish_payload(language="fr"),
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_finish_requires_auth(client, app_settings):
    app_settings(AZURE_SPEECH_KEY="dummy-key")
    r = await client.post("/api/v1/speak/finish", json=_finish_payload())
    assert r.status_code == 401
