from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import case, func, select

from klara.config import get_settings
from klara.dependencies import DBSession, LocaleDep, SettingsDep
from klara.i18n import t
from klara.models import AudioCache
from klara.services.tts_service import get_or_synthesize
from klara.tts import ElevenLabsTTS, InworldTTS, TTSError, TTSProvider

router = APIRouter(prefix="/tts", tags=["tts"])


def _build_provider(settings, locale: str) -> TTSProvider:
    if settings.tts_provider == "elevenlabs":
        return ElevenLabsTTS(settings)
    if settings.tts_provider == "inworld":
        return InworldTTS(settings)
    raise HTTPException(
        status_code=503,
        detail=t("errors.tts_provider_unsupported", locale, provider=settings.tts_provider),
    )


@router.get("")
async def synthesize(
    db: DBSession,
    settings: SettingsDep,
    locale: LocaleDep,
    text: str = Query(..., min_length=1),
    voice: str | None = Query(None),
    lang: str | None = Query(None, max_length=8),
    mode: str = Query("narration", pattern="^(narration|realtime)$"),
) -> Response:
    """`mode=realtime` (Speak replies) uses the low-latency model; the default
    `narration` serves everything a learner re-listens to — story sentences,
    word audio — on the expressive model. Old cached frontends that don't send
    `mode` just get narration quality everywhere, which is safe."""
    if len(text) > settings.tts_max_text_chars:
        raise HTTPException(
            status_code=413,
            detail=t("errors.tts_text_too_long", locale, max=settings.tts_max_text_chars),
        )

    try:
        provider = _build_provider(settings, locale)
    except TTSError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    try:
        audio, mime, hit = await get_or_synthesize(
            db,
            provider,
            text=text,
            voice_id=voice,
            lang=lang,
            narration=mode != "realtime",
        )
    except TTSError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return Response(
        content=audio,
        media_type=mime,
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "X-TTS-Cache": "HIT" if hit else "MISS",
        },
    )


@router.get("/health")
async def tts_health() -> dict[str, str]:
    settings = get_settings()
    if settings.tts_provider == "elevenlabs" and not settings.elevenlabs_api_key:
        return {"status": "missing_key", "provider": settings.tts_provider}
    if settings.tts_provider == "inworld" and not settings.inworld_api_key:
        return {"status": "missing_key", "provider": settings.tts_provider}
    return {"status": "ok", "provider": settings.tts_provider}


@router.get("/stats")
async def tts_stats(db: DBSession) -> dict:
    # ElevenLabs bills flash/turbo at 0.5 credits per character, everything
    # else (multilingual v2, v3) at 1.0 — estimate per row now that narration
    # and realtime audio live on different models.
    credit_factor = case(
        (AudioCache.model.like("%flash%"), 0.5),
        (AudioCache.model.like("%turbo%"), 0.5),
        else_=1.0,
    )
    row = (
        await db.execute(
            select(
                func.count(AudioCache.id),
                func.coalesce(func.sum(AudioCache.char_count), 0),
                func.coalesce(func.sum(AudioCache.access_count), 0),
                func.coalesce(func.sum(AudioCache.access_count - 1), 0),
                func.coalesce(func.sum(AudioCache.char_count * credit_factor), 0),
                func.coalesce(
                    func.sum((AudioCache.access_count - 1) * AudioCache.char_count * credit_factor),
                    0,
                ),
            )
        )
    ).one()
    entries, chars_synthesized, total_plays, replays, credits_used, credits_saved = row
    return {
        "entries": int(entries),
        "chars_synthesized": int(chars_synthesized),
        "total_plays": int(total_plays),
        "replays_from_cache": int(replays),
        "estimated_credits_used": round(float(credits_used), 1),
        "estimated_credits_saved_by_cache": round(float(credits_saved), 1),
    }
