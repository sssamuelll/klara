import asyncio

import structlog

from klara.config import Settings
from klara.db import get_sessionmaker
from klara.services.tts_service import get_or_synthesize
from klara.tts import ElevenLabsTTS, InworldTTS, TTSError, TTSProvider

log = structlog.get_logger(__name__)

_TTS_CONCURRENCY = 3


def _build_provider(settings: Settings) -> TTSProvider | None:
    try:
        if settings.tts_provider == "elevenlabs":
            return ElevenLabsTTS(settings)
        if settings.tts_provider == "inworld":
            return InworldTTS(settings)
        log.warning("tts.precache.unsupported_provider", provider=settings.tts_provider)
        return None
    except TTSError as e:
        log.warning("tts.precache.provider_init_failed", error=str(e))
        return None


def collect_story_sequence(story_content: dict, title: str | None = None) -> list[str]:
    """The story in read-aloud order — title first, then each sentence.

    Order matters: each item's neighbors become previous_text/next_text
    context at synthesis time, so a sentence is intoned as part of the
    passage instead of in isolation.
    """
    sequence: list[str] = []
    if title and title.strip():
        sequence.append(title.strip())
    for s in story_content.get("sentences") or []:
        target = (s.get("target") or "").strip()
        if target:
            sequence.append(target)
    return sequence


def collect_extra_texts(target_words: list[dict] | None) -> list[str]:
    """Standalone dictionary audio — word examples and bare lemmas. These are
    deliberately synthesized WITHOUT passage context."""
    texts: list[str] = []
    if target_words:
        for w in target_words:
            example = (w.get("example_target") or "").strip()
            if example:
                texts.append(example)
            lemma = (w.get("lemma") or "").strip()
            if lemma:
                texts.append(lemma)
    seen: set[str] = set()
    deduped: list[str] = []
    for t in texts:
        if t not in seen:
            seen.add(t)
            deduped.append(t)
    return deduped


async def precache_story(
    settings: Settings,
    story_content: dict,
    target_words: list[dict] | None = None,
    title: str | None = None,
    lang: str | None = None,
) -> None:
    provider = _build_provider(settings)
    if provider is None:
        return

    try:
        sm = get_sessionmaker()
    except RuntimeError:
        log.warning("tts.precache.no_db")
        return

    sequence = collect_story_sequence(story_content, title)
    in_sequence = set(sequence)
    extras = [t for t in collect_extra_texts(target_words) if t not in in_sequence]

    semaphore = asyncio.Semaphore(_TTS_CONCURRENCY)

    async def one(text: str, previous_text: str | None, next_text: str | None) -> None:
        async with semaphore:
            async with sm() as session:
                try:
                    _, _, hit = await get_or_synthesize(
                        session,
                        provider,
                        text=text,
                        lang=lang,
                        narration=True,
                        previous_text=previous_text,
                        next_text=next_text,
                    )
                    log.debug("tts.precache.done", chars=len(text), cache_hit=hit)
                except TTSError as e:
                    log.warning("tts.precache.failed", error=str(e), chars=len(text))
                except Exception as e:
                    log.warning("tts.precache.unexpected", error=str(e), chars=len(text))

    tasks = []
    scheduled: set[str] = set()
    for i, text in enumerate(sequence):
        # A repeated sentence (or a title equal to a sentence) shares the same
        # cache key; concurrent tasks would BOTH miss and pay double synthesis.
        # First occurrence's context wins — consistent with the cache design.
        if text in scheduled:
            continue
        scheduled.add(text)
        prev = sequence[i - 1] if i > 0 else None
        nxt = sequence[i + 1] if i + 1 < len(sequence) else None
        tasks.append(one(text, prev, nxt))
    tasks.extend(one(t, None, None) for t in extras)

    log.info("tts.precache.start", sentences=len(sequence), extras=len(extras))
    await asyncio.gather(*tasks)
    log.info("tts.precache.complete", count=len(sequence) + len(extras))
