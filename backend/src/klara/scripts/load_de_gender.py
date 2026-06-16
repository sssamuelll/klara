"""Load the authoritative German gender oracle from the gambolputty/german-nouns
CSV into the gender_lexicon table.

Usage:
    uv run python -m klara.scripts.load_de_gender <path-to-nouns.csv>

The dataset (https://github.com/gambolputty/german-nouns, CC-BY-SA 4.0) is
acquired separately and attributed in NOTICE; this script does not vendor it.
Idempotent wrapper over curriculum.gender_lex.load_gender_lexicon.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from klara.config import get_settings
from klara.curriculum.gender_lex import load_gender_lexicon, parse_gender_csv
from klara.db import dispose_engine, get_sessionmaker, init_engine


async def _run(path: Path) -> None:
    rows = parse_gender_csv(path.read_text(encoding="utf-8"))
    settings = get_settings()
    init_engine(settings)
    try:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as db:
            await load_gender_lexicon(db, rows=rows)
            await db.commit()
        # Report the row count from `rows` (file-derived), not the loader's
        # return: the return value's taint includes the db session (built from
        # DATABASE_URL), which trips CodeQL's clear-text-logging query.
        print(f"Cargadas {len(rows)} entradas de género (de).")
    finally:
        await dispose_engine()


def main() -> None:
    if len(sys.argv) != 2:
        print("uso: python -m klara.scripts.load_de_gender <ruta-al-csv>", file=sys.stderr)
        raise SystemExit(2)
    asyncio.run(_run(Path(sys.argv[1])))


if __name__ == "__main__":
    main()
