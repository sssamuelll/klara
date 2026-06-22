"""Carga la lista de frecuencia léxica de alemán al inventario.

Uso:
    uv run python -m klara.scripts.load_de_lexical <ruta-al-tsv>

El TSV es `lemma<TAB>pos<TAB>cefr<TAB>rank` (con cabecera). La lista real
(Kelly / SUBTLEX-DE + CEFR) se adquiere aparte por licencia (atribuida en
NOTICE); este script NO la incluye. Wrapper idempotente sobre
curriculum.inventory.load_frequency.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from klara.config import get_settings
from klara.curriculum.inventory import load_frequency, parse_frequency_tsv
from klara.db import dispose_engine, get_sessionmaker, init_engine


async def _run(path: Path) -> None:
    rows = parse_frequency_tsv(path.read_text(encoding="utf-8"))
    settings = get_settings()
    init_engine(settings)
    try:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as db:
            n = await load_frequency(db, language="de", rows=rows)
        print(f"Cargadas {n} filas de frecuencia (de).")
    finally:
        await dispose_engine()


def main() -> None:
    if len(sys.argv) != 2:
        print("uso: python -m klara.scripts.load_de_lexical <ruta-al-tsv>", file=sys.stderr)
        raise SystemExit(2)
    asyncio.run(_run(Path(sys.argv[1])))


if __name__ == "__main__":
    main()
