"""Seed the curated ES->DE gender L1-transfer notes (es).

Usage:
    uv run python -m klara.scripts.load_de_l1_notes

Hand-authored, corpus-complete over the A1 corpus (load_de_modules.py): the
genuine ES<->DE gender clashes among its nouns. Idempotent (re-run safe; edits
update). The DE article is rendered by the frontend from the oracle, so the note
prose does not repeat it.
"""

from __future__ import annotations

import asyncio

from klara.config import get_settings
from klara.curriculum.l1_notes import L1NoteRow, load_l1_notes
from klara.db import dispose_engine, get_sessionmaker, init_engine

_ES_NOTES: list[tuple[str, str]] = [
    ("Tisch", "En español «la mesa» es femenino, pero en alemán es masculino."),
    ("Stuhl", "En español «la silla» es femenino, pero en alemán es masculino."),
    ("Apfel", "En español «la manzana» es femenino, pero en alemán es masculino."),
    ("Bahnhof", "En español «la estación» es femenino, pero en alemán es masculino."),
    ("Auto", "En español «el coche» es masculino, pero en alemán es neutro."),
    ("Geld", "En español «el dinero» es masculino, pero en alemán es neutro."),
    ("Jahr", "En español «el año» es masculino, pero en alemán es neutro."),
    ("Brot", "En español «el pan» es masculino, pero en alemán es neutro."),
    ("Land", "En español «el país» es masculino, pero en alemán es neutro."),
    ("Haus", "En español «la casa» es femenino, pero en alemán es neutro."),
    ("Bett", "En español «la cama» es femenino, pero en alemán es neutro."),
    ("Fenster", "En español «la ventana» es femenino, pero en alemán es neutro."),
    ("Zimmer", "En español «la habitación» es femenino, pero en alemán es neutro."),
    ("Geschäft", "En español «la tienda» es femenino, pero en alemán es neutro."),
    ("Fahrrad", "En español «la bicicleta» es femenino, pero en alemán es neutro."),
    ("Minute", "En español «el minuto» es masculino, pero en alemán es femenino."),
    ("Sprache", "En español «el idioma» es masculino, pero en alemán es femenino."),
    ("Wohnung", "En español «el piso» es masculino, pero en alemán es femenino."),
    ("Zahl", "En español «el número» es masculino, pero en alemán es femenino."),
    ("Bahn", "En español «el tren» es masculino, pero en alemán es femenino."),
]


async def _run() -> None:
    rows = [L1NoteRow(lemma=lemma, l1_language="es", note=note) for lemma, note in _ES_NOTES]
    settings = get_settings()
    init_engine(settings)
    try:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as db:
            n = await load_l1_notes(db, rows=rows)
            await db.commit()
        print(f"Cargadas {n} notas de trampa de género (es).")
    finally:
        await dispose_engine()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
