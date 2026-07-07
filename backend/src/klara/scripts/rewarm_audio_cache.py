"""One-time audio-cache re-warm after a TTS model change.

The audio_cache hash keys on the model, so changing models orphans every
existing row. Without this re-warm, the first replay of a pre-existing story
falls back to on-demand, context-FREE synthesis — and because context is not
part of the cache key, that isolated rendition permanently claims the
narration slot for its sentence. Re-warming through precache_story gives
every sentence the narration model plus neighbor context before anyone plays
it. Idempotent: already-cached texts are skipped.

Run on the box right after deploying a model change:

    docker exec -it $(docker ps -qf "name=backend") \
        uv run python -m klara.scripts.rewarm_audio_cache

Afterwards, optionally reclaim the previous model's dead rows:

    DELETE FROM audio_cache WHERE model = 'eleven_turbo_v2_5';
"""

import asyncio

from sqlalchemy import select

from klara.config import get_settings
from klara.db import dispose_engine, get_sessionmaker, init_engine
from klara.models import Story, StoryLibrary
from klara.services.tts_precache import precache_story


async def _run() -> None:
    settings = get_settings()
    init_engine(settings)
    try:
        sm = get_sessionmaker()
        async with sm() as db:
            stories = list((await db.execute(select(Story))).scalars())
            library = list((await db.execute(select(StoryLibrary))).scalars())

        # (content, title, lang) triples; word audio is deliberately skipped —
        # lemmas/examples are context-free, so on-demand synthesis produces
        # identical cache entries anyway.
        items = [(s.content, s.title, s.target_language) for s in stories]
        items += [(s.content, s.title, s.language) for s in library]

        for i, (content, title, lang) in enumerate(items, start=1):
            await precache_story(settings, content, None, title, lang)
            print(f"[{i}/{len(items)}] {title}")
        print(f"Re-warm listo: {len(items)} historia(s).")
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(_run())
