"""Story precache: sentences are synthesized on the narration tier carrying
their neighbors as prosody context (so each one is intoned as part of the
passage), while word examples and lemmas stay deliberately context-free.
"""

from __future__ import annotations

from klara.config import Settings
from klara.services import tts_precache


def _settings() -> Settings:
    return Settings(
        tts_provider="elevenlabs",
        elevenlabs_api_key="test-key",
        elevenlabs_voice_id="FALLBACK",
    )


class _FakeSessionCM:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *exc) -> bool:
        return False


def test_collect_story_sequence_orders_title_then_sentences():
    content = {"sentences": [{"target": "S1."}, {"target": " "}, {"target": "S2?"}]}
    assert tts_precache.collect_story_sequence(content, "Titel") == ["Titel", "S1.", "S2?"]
    assert tts_precache.collect_story_sequence(content, None) == ["S1.", "S2?"]


async def test_precache_story_contextualizes_sentences(monkeypatch):
    calls: list[dict] = []

    async def fake_get_or_synthesize(
        session,
        provider,
        *,
        text,
        voice_id=None,
        lang=None,
        narration=False,
        previous_text=None,
        next_text=None,
    ):
        calls.append(
            {
                "text": text,
                "lang": lang,
                "narration": narration,
                "previous_text": previous_text,
                "next_text": next_text,
            }
        )
        return b"", "audio/mpeg", False

    monkeypatch.setattr(tts_precache, "get_or_synthesize", fake_get_or_synthesize)
    monkeypatch.setattr(tts_precache, "get_sessionmaker", lambda: lambda: _FakeSessionCM())

    content = {
        "sentences": [
            {"target": "S1."},
            {"target": "S2?"},
            # Repeated refrain: same cache key as the first occurrence — a
            # second concurrent task would double-bill the synthesis.
            {"target": "S1."},
            {"target": "S3."},
        ]
    }
    # "S1." as a lemma collides with a sentence — must NOT synthesize twice.
    words = [
        {"lemma": "S1.", "example_target": "Ein Beispiel."},
        {"lemma": "Wort", "example_target": ""},
    ]
    await tts_precache.precache_story(_settings(), content, words, title="Titel", lang="de")

    by_text = {c["text"]: c for c in calls}
    assert len(calls) == len(by_text), "no text synthesized twice"

    # Sequence: title leads into the first sentence; edges have open ends.
    assert by_text["Titel"]["previous_text"] is None
    assert by_text["Titel"]["next_text"] == "S1."
    assert by_text["S1."]["previous_text"] == "Titel"
    assert by_text["S1."]["next_text"] == "S2?"
    assert by_text["S2?"]["previous_text"] == "S1."
    # The repeated occurrence still serves as its neighbors' context even
    # though it is not synthesized again itself.
    assert by_text["S2?"]["next_text"] == "S1."
    assert by_text["S3."]["previous_text"] == "S1."
    assert by_text["S3."]["next_text"] is None
    # And the refrain was synthesized exactly once, with the FIRST
    # occurrence's context (Titel → S2?).
    assert by_text["S1."]["next_text"] == "S2?"

    # Everything precached rides the narration tier with the story's lang.
    assert all(c["narration"] for c in calls)
    assert all(c["lang"] == "de" for c in calls)

    # Extras: present, context-free; empty example skipped.
    assert by_text["Ein Beispiel."]["previous_text"] is None
    assert by_text["Ein Beispiel."]["next_text"] is None
    assert by_text["Wort"]["previous_text"] is None
    assert "" not in by_text


async def test_precache_story_survives_per_item_errors(monkeypatch):
    """One failed synthesis must not sink the rest of the story's audio."""
    calls: list[str] = []

    async def flaky_get_or_synthesize(session, provider, *, text, **kwargs):
        if text == "S1.":
            raise tts_precache.TTSError("boom")
        calls.append(text)
        return b"", "audio/mpeg", False

    monkeypatch.setattr(tts_precache, "get_or_synthesize", flaky_get_or_synthesize)
    monkeypatch.setattr(tts_precache, "get_sessionmaker", lambda: lambda: _FakeSessionCM())

    content = {"sentences": [{"target": "S1."}, {"target": "S2?"}]}
    await tts_precache.precache_story(_settings(), content, None, title=None, lang="de")

    assert calls == ["S2?"]
