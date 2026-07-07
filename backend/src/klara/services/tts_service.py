import hashlib
from datetime import UTC, datetime

import structlog
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from klara.models import AudioCache
from klara.tts.base import TTSProvider, TTSResult

log = structlog.get_logger(__name__)


def _hash_request(*, provider: str, model: str, voice_id: str, text: str) -> str:
    raw = f"{provider}|{model}|{voice_id}|{text}".encode()
    return hashlib.sha256(raw).hexdigest()


async def get_or_synthesize(
    db: AsyncSession,
    tts: TTSProvider,
    *,
    text: str,
    voice_id: str | None = None,
    lang: str | None = None,
    narration: bool = False,
    previous_text: str | None = None,
    next_text: str | None = None,
) -> tuple[bytes, str, bool]:
    """Returns (audio_bytes, mime_type, was_cache_hit).

    `lang` (ISO 639-1) lets the provider pick a language-native voice;
    explicit `voice_id` always wins. The resolved voice goes into the cache
    hash, so per-language voices land in separate cache entries.

    `narration=True` selects the provider's expressive narration model — the
    hash keys on the model actually used, so narration and realtime audio for
    the same text are separate cache entries. `previous_text`/`next_text`
    deliberately do NOT enter the hash: the same sentence appearing in two
    stories reuses whichever intonation got cached first — an accepted
    trade-off, far better than every sentence sounding isolated.
    """
    text = text.strip()
    voice = voice_id or tts.voice_for_lang(lang)
    model = tts.narration_model if narration else tts.model
    text_hash = _hash_request(provider=tts.name, model=model, voice_id=voice, text=text)

    cached = (
        await db.execute(select(AudioCache).where(AudioCache.text_hash == text_hash))
    ).scalar_one_or_none()
    if cached is not None:
        await db.execute(
            update(AudioCache)
            .where(AudioCache.id == cached.id)
            .values(
                access_count=AudioCache.access_count + 1,
                last_accessed_at=datetime.now(UTC),
            )
        )
        await db.commit()
        log.debug("tts.cache.hit", hash=text_hash[:8], chars=len(text))
        return cached.audio_data, cached.mime_type, True

    log.info("tts.cache.miss", hash=text_hash[:8], chars=len(text), provider=tts.name)
    result: TTSResult = await tts.synthesize(
        text,
        voice_id=voice,
        narration=narration,
        previous_text=previous_text,
        next_text=next_text,
    )

    stmt = (
        pg_insert(AudioCache)
        .values(
            text_hash=text_hash,
            text=text,
            provider=result.provider,
            model=result.model,
            voice_id=result.voice_id,
            mime_type=result.mime_type,
            audio_data=result.audio,
            char_count=result.char_count,
        )
        .on_conflict_do_update(
            index_elements=["text_hash"],
            set_={
                "access_count": AudioCache.access_count + 1,
                "last_accessed_at": datetime.now(UTC),
            },
        )
    )
    await db.execute(stmt)
    await db.commit()
    return result.audio, result.mime_type, False
