"""Seed the curated German A1 module sequence.

Usage:
    uv run python -m klara.scripts.load_de_modules

PR-A seeds ONE module ("En el café") to prove the loop end-to-end. The full
A1 sequence (PR-B) extends MODULES below. Idempotent — safe to re-run.
"""

from __future__ import annotations

import asyncio

from klara.config import get_settings
from klara.curriculum.modules import load_modules
from klara.db import dispose_engine, get_sessionmaker, init_engine

MODULES: list[dict] = [
    {
        "sequence_order": 1,
        "title": "En el café",
        "cefr_level": "A1",
        "can_dos": ["puedo pedir una bebida o un dulce en un café"],
        "grammatical_focus": ["género de sustantivos de comida y bebida (der/die/das)"],
        "vocab": [
            {"lemma": "Kaffee", "pos": "noun", "gender": "der", "translations": {"es": "café"}},
            {"lemma": "Tee", "pos": "noun", "gender": "der", "translations": {"es": "té"}},
            {"lemma": "Wasser", "pos": "noun", "gender": "das", "translations": {"es": "agua"}},
            {"lemma": "Milch", "pos": "noun", "gender": "die", "translations": {"es": "leche"}},
            {"lemma": "Tasse", "pos": "noun", "gender": "die", "translations": {"es": "taza"}},
            {"lemma": "Kuchen", "pos": "noun", "gender": "der", "translations": {"es": "pastel"}},
            {"lemma": "Brot", "pos": "noun", "gender": "das", "translations": {"es": "pan"}},
            {"lemma": "Zucker", "pos": "noun", "gender": "der", "translations": {"es": "azúcar"}},
            {"lemma": "bestellen", "pos": "verb", "translations": {"es": "pedir/ordenar"}},
            {"lemma": "trinken", "pos": "verb", "translations": {"es": "beber"}},
        ],
    }
]


async def _run() -> None:
    settings = get_settings()
    init_engine(settings)
    try:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as db:
            n = await load_modules(db, language="de", modules=MODULES)
            await db.commit()
        print(f"Sembrados {n} módulo(s) de alemán.")
    finally:
        await dispose_engine()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
