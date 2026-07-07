"""get_or_synthesize cache-key semantics for the narration/realtime split.

The hash keys on the model actually used, so narration and realtime audio of
the same text are distinct cache entries — while neighbor-sentence context is
deliberately NOT part of the key (same sentence in two stories reuses the
first cached intonation).
"""

from __future__ import annotations

from uuid import uuid4

from klara.services.tts_service import get_or_synthesize
from klara.tts.base import TTSResult


class FakeTTS:
    name = "fake"
    model = "rt-model"
    narration_model = "narr-model"
    default_voice_id = "v1"

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def voice_for_lang(self, lang):
        return self.default_voice_id

    async def synthesize(
        self,
        text,
        voice_id=None,
        *,
        narration=False,
        previous_text=None,
        next_text=None,
    ) -> TTSResult:
        self.calls.append({"text": text, "narration": narration, "previous_text": previous_text})
        return TTSResult(
            audio=b"x",
            mime_type="audio/mpeg",
            provider=self.name,
            model=self.narration_model if narration else self.model,
            voice_id=voice_id or self.default_voice_id,
            char_count=len(text),
        )


async def test_narration_and_realtime_are_separate_cache_entries(db_session):
    tts = FakeTTS()
    text = f"Hallo {uuid4()}."

    _, _, hit1 = await get_or_synthesize(db_session, tts, text=text, narration=True)
    _, _, hit2 = await get_or_synthesize(db_session, tts, text=text, narration=False)
    assert hit1 is False
    assert hit2 is False, "realtime must not reuse the narration entry"

    _, _, hit3 = await get_or_synthesize(db_session, tts, text=text, narration=True)
    assert hit3 is True, "same tier re-request hits the cache"

    assert [c["narration"] for c in tts.calls] == [True, False]


async def test_context_is_forwarded_but_not_part_of_the_key(db_session):
    tts = FakeTTS()
    text = f"Ich bin dran {uuid4()}."

    _, _, hit1 = await get_or_synthesize(
        db_session, tts, text=text, narration=True, previous_text="A.", next_text="B."
    )
    assert hit1 is False
    assert tts.calls[0]["previous_text"] == "A."

    # Different context, same text+tier → cache hit, no second synthesis.
    _, _, hit2 = await get_or_synthesize(
        db_session, tts, text=text, narration=True, previous_text="C.", next_text=None
    )
    assert hit2 is True
    assert len(tts.calls) == 1
