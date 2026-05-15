import asyncio

import structlog

from german_app.config import Settings
from german_app.db import get_sessionmaker
from german_app.services.tts_service import get_or_synthesize
from german_app.tts.base import TTSProvider
from german_app.tts.elevenlabs_impl import ElevenLabsTTS, ElevenLabsTTSError

log = structlog.get_logger(__name__)

_TTS_CONCURRENCY = 3


def _build_provider(settings: Settings) -> TTSProvider | None:
    if settings.tts_provider != "elevenlabs":
        log.warning("tts.precache.unsupported_provider", provider=settings.tts_provider)
        return None
    try:
        return ElevenLabsTTS(settings)
    except ElevenLabsTTSError as e:
        log.warning("tts.precache.provider_init_failed", error=str(e))
        return None


def collect_story_texts(story_content: dict, target_words: list[dict] | None = None) -> list[str]:
    texts: list[str] = []
    sentences = story_content.get("sentences") or []
    for s in sentences:
        target = (s.get("target") or "").strip()
        if target:
            texts.append(target)
    if target_words:
        for w in target_words:
            example = (w.get("example_target") or "").strip()
            if example:
                texts.append(example)
            lemma = (w.get("lemma") or "").strip()
            if lemma and lemma not in texts:
                texts.append(lemma)
    seen: set[str] = set()
    deduped: list[str] = []
    for t in texts:
        if t not in seen:
            seen.add(t)
            deduped.append(t)
    return deduped


async def precache_texts(settings: Settings, texts: list[str]) -> None:
    if not texts:
        return
    provider = _build_provider(settings)
    if provider is None:
        return

    try:
        sm = get_sessionmaker()
    except RuntimeError:
        log.warning("tts.precache.no_db")
        return

    semaphore = asyncio.Semaphore(_TTS_CONCURRENCY)

    async def one(text: str) -> None:
        async with semaphore:
            async with sm() as session:
                try:
                    _, _, hit = await get_or_synthesize(session, provider, text=text)
                    log.debug("tts.precache.done", chars=len(text), cache_hit=hit)
                except ElevenLabsTTSError as e:
                    log.warning("tts.precache.failed", error=str(e), chars=len(text))
                except Exception as e:
                    log.warning("tts.precache.unexpected", error=str(e), chars=len(text))

    log.info("tts.precache.start", count=len(texts))
    await asyncio.gather(*(one(t) for t in texts))
    log.info("tts.precache.complete", count=len(texts))
