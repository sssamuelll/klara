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
    },
    {
        "sequence_order": 2,
        "title": "Saludos y presentarse",
        "cefr_level": "A1",
        "can_dos": ["puedo saludar y despedirme", "puedo decir mi nombre y de dónde soy"],
        "grammatical_focus": ["verbos sein y heißen", "pronombres ich/du/Sie"],
        "vocab": [
            {"lemma": "Name", "pos": "noun", "gender": "der", "translations": {"es": "nombre"}},
            {"lemma": "Sprache", "pos": "noun", "gender": "die", "translations": {"es": "idioma"}},
            {"lemma": "Land", "pos": "noun", "gender": "das", "translations": {"es": "país"}},
            {"lemma": "Stadt", "pos": "noun", "gender": "die", "translations": {"es": "ciudad"}},
            {"lemma": "Freund", "pos": "noun", "gender": "der", "translations": {"es": "amigo"}},
            {"lemma": "heißen", "pos": "verb", "translations": {"es": "llamarse"}},
            {"lemma": "kommen", "pos": "verb", "translations": {"es": "venir"}},
            {"lemma": "wohnen", "pos": "verb", "translations": {"es": "vivir/residir"}},
            {"lemma": "sprechen", "pos": "verb", "translations": {"es": "hablar"}},
        ],
    },
    {
        "sequence_order": 3,
        "title": "La familia",
        "cefr_level": "A1",
        "can_dos": ["puedo hablar de mi familia", "puedo decir quién es quién"],
        "grammatical_focus": ["género de los miembros de la familia", "posesivos mein/dein"],
        "vocab": [
            {"lemma": "Vater", "pos": "noun", "gender": "der", "translations": {"es": "padre"}},
            {"lemma": "Mutter", "pos": "noun", "gender": "die", "translations": {"es": "madre"}},
            {"lemma": "Kind", "pos": "noun", "gender": "das", "translations": {"es": "niño/a"}},
            {"lemma": "Bruder", "pos": "noun", "gender": "der", "translations": {"es": "hermano"}},
            {
                "lemma": "Schwester",
                "pos": "noun",
                "gender": "die",
                "translations": {"es": "hermana"},
            },
            {"lemma": "Familie", "pos": "noun", "gender": "die", "translations": {"es": "familia"}},
            {"lemma": "Sohn", "pos": "noun", "gender": "der", "translations": {"es": "hijo"}},
            {"lemma": "Tochter", "pos": "noun", "gender": "die", "translations": {"es": "hija"}},
        ],
    },
    {
        "sequence_order": 4,
        "title": "Números y la hora",
        "cefr_level": "A1",
        "can_dos": ["puedo contar y usar números", "puedo preguntar y decir la hora"],
        "grammatical_focus": ["números cardinales", "decir la hora (Wie spät ist es?)"],
        "vocab": [
            {"lemma": "Uhr", "pos": "noun", "gender": "die", "translations": {"es": "reloj/hora"}},
            {"lemma": "Stunde", "pos": "noun", "gender": "die", "translations": {"es": "hora"}},
            {"lemma": "Minute", "pos": "noun", "gender": "die", "translations": {"es": "minuto"}},
            {"lemma": "Tag", "pos": "noun", "gender": "der", "translations": {"es": "día"}},
            {"lemma": "Woche", "pos": "noun", "gender": "die", "translations": {"es": "semana"}},
            {"lemma": "Monat", "pos": "noun", "gender": "der", "translations": {"es": "mes"}},
            {"lemma": "Jahr", "pos": "noun", "gender": "das", "translations": {"es": "año"}},
            {"lemma": "Zahl", "pos": "noun", "gender": "die", "translations": {"es": "número"}},
        ],
    },
    {
        "sequence_order": 5,
        "title": "De compras",
        "cefr_level": "A1",
        "can_dos": ["puedo comprar comida y cosas básicas", "puedo preguntar el precio"],
        "grammatical_focus": ["género de productos comunes", "plural de sustantivos"],
        "vocab": [
            {"lemma": "Markt", "pos": "noun", "gender": "der", "translations": {"es": "mercado"}},
            {"lemma": "Geschäft", "pos": "noun", "gender": "das", "translations": {"es": "tienda"}},
            {"lemma": "Tasche", "pos": "noun", "gender": "die", "translations": {"es": "bolsa"}},
            {"lemma": "Geld", "pos": "noun", "gender": "das", "translations": {"es": "dinero"}},
            {"lemma": "Preis", "pos": "noun", "gender": "der", "translations": {"es": "precio"}},
            {"lemma": "Apfel", "pos": "noun", "gender": "der", "translations": {"es": "manzana"}},
            {"lemma": "kaufen", "pos": "verb", "translations": {"es": "comprar"}},
            {"lemma": "bezahlen", "pos": "verb", "translations": {"es": "pagar"}},
        ],
    },
    {
        "sequence_order": 6,
        "title": "La casa",
        "cefr_level": "A1",
        "can_dos": [
            "puedo nombrar las habitaciones de la casa",
            "puedo decir dónde están las cosas",
        ],
        "grammatical_focus": [
            "género de objetos del hogar",
            "preposiciones de lugar (in/auf/unter)",
        ],
        "vocab": [
            {"lemma": "Haus", "pos": "noun", "gender": "das", "translations": {"es": "casa"}},
            {
                "lemma": "Wohnung",
                "pos": "noun",
                "gender": "die",
                "translations": {"es": "piso/apartamento"},
            },
            {
                "lemma": "Zimmer",
                "pos": "noun",
                "gender": "das",
                "translations": {"es": "habitación"},
            },
            {"lemma": "Küche", "pos": "noun", "gender": "die", "translations": {"es": "cocina"}},
            {"lemma": "Tisch", "pos": "noun", "gender": "der", "translations": {"es": "mesa"}},
            {"lemma": "Stuhl", "pos": "noun", "gender": "der", "translations": {"es": "silla"}},
            {"lemma": "Bett", "pos": "noun", "gender": "das", "translations": {"es": "cama"}},
            {"lemma": "Tür", "pos": "noun", "gender": "die", "translations": {"es": "puerta"}},
            {"lemma": "Fenster", "pos": "noun", "gender": "das", "translations": {"es": "ventana"}},
        ],
    },
    {
        "sequence_order": 7,
        "title": "La rutina diaria",
        "cefr_level": "A1",
        "can_dos": ["puedo describir mi rutina diaria", "puedo decir qué hago cada día"],
        "grammatical_focus": ["verbos separables (aufstehen)", "partes del día"],
        "vocab": [
            {"lemma": "Morgen", "pos": "noun", "gender": "der", "translations": {"es": "mañana"}},
            {
                "lemma": "Abend",
                "pos": "noun",
                "gender": "der",
                "translations": {"es": "tarde/noche"},
            },
            {"lemma": "Nacht", "pos": "noun", "gender": "die", "translations": {"es": "noche"}},
            {"lemma": "aufstehen", "pos": "verb", "translations": {"es": "levantarse"}},
            {"lemma": "frühstücken", "pos": "verb", "translations": {"es": "desayunar"}},
            {"lemma": "arbeiten", "pos": "verb", "translations": {"es": "trabajar"}},
            {"lemma": "schlafen", "pos": "verb", "translations": {"es": "dormir"}},
            {"lemma": "essen", "pos": "verb", "translations": {"es": "comer"}},
        ],
    },
    {
        "sequence_order": 8,
        "title": "Moverse por la ciudad",
        "cefr_level": "A1",
        "can_dos": ["puedo moverme por la ciudad", "puedo preguntar cómo llegar a un lugar"],
        "grammatical_focus": ["género de transportes y lugares", "dativo con mit (mit dem Bus)"],
        "vocab": [
            {"lemma": "Bus", "pos": "noun", "gender": "der", "translations": {"es": "autobús"}},
            {
                "lemma": "Bahn",
                "pos": "noun",
                "gender": "die",
                "translations": {"es": "tren/tranvía"},
            },
            {"lemma": "Auto", "pos": "noun", "gender": "das", "translations": {"es": "coche"}},
            {"lemma": "Straße", "pos": "noun", "gender": "die", "translations": {"es": "calle"}},
            {
                "lemma": "Bahnhof",
                "pos": "noun",
                "gender": "der",
                "translations": {"es": "estación"},
            },
            {"lemma": "Weg", "pos": "noun", "gender": "der", "translations": {"es": "camino"}},
            {
                "lemma": "Fahrrad",
                "pos": "noun",
                "gender": "das",
                "translations": {"es": "bicicleta"},
            },
            {"lemma": "fahren", "pos": "verb", "translations": {"es": "ir/conducir"}},
        ],
    },
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
