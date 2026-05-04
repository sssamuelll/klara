from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import func, select

from german_app.config import get_settings
from german_app.dependencies import DBSession, SettingsDep
from german_app.models import AudioCache
from german_app.services.tts_service import get_or_synthesize
from german_app.tts.elevenlabs_impl import ElevenLabsTTS, ElevenLabsTTSError

router = APIRouter(prefix="/tts", tags=["tts"])


def _build_provider(settings):
    if settings.tts_provider == "elevenlabs":
        return ElevenLabsTTS(settings)
    raise HTTPException(status_code=503, detail=f"Unsupported TTS provider: {settings.tts_provider}")


@router.get("")
async def synthesize(
    db: DBSession,
    settings: SettingsDep,
    text: str = Query(..., min_length=1),
    voice: str | None = Query(None),
) -> Response:
    if len(text) > settings.tts_max_text_chars:
        raise HTTPException(
            status_code=413,
            detail=f"Text too long (>{settings.tts_max_text_chars} chars)",
        )

    try:
        provider = _build_provider(settings)
    except ElevenLabsTTSError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    try:
        audio, mime, hit = await get_or_synthesize(db, provider, text=text, voice_id=voice)
    except ElevenLabsTTSError as e:
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
    return {"status": "ok", "provider": settings.tts_provider}


@router.get("/stats")
async def tts_stats(db: DBSession) -> dict:
    row = (
        await db.execute(
            select(
                func.count(AudioCache.id),
                func.coalesce(func.sum(AudioCache.char_count), 0),
                func.coalesce(func.sum(AudioCache.access_count), 0),
                func.coalesce(func.sum(AudioCache.access_count - 1), 0),
            )
        )
    ).one()
    entries, chars_synthesized, total_plays, replays = row
    estimated_credits_used = chars_synthesized * 0.5
    estimated_credits_saved = (replays or 0) * (chars_synthesized / max(entries, 1)) * 0.5
    return {
        "entries": int(entries),
        "chars_synthesized": int(chars_synthesized),
        "total_plays": int(total_plays),
        "replays_from_cache": int(replays),
        "estimated_credits_used": round(estimated_credits_used, 1),
        "estimated_credits_saved_by_cache": round(estimated_credits_saved, 1),
    }
