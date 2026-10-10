"""El contenido de cada actividad, generado del catálogo (spec §3.1). Las
lecciones y los repasos usan los mismos generadores, así nunca se separan.

Los distractores salen solo de lo que ya se presentó (`Contexto.conocidos`): una
opción que nunca viste no enseña nada."""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass

from klara.catalogo.modelo import Actividad, Catalogo, Kana

TABLERO_SEGUNDOS = 45


@dataclass(frozen=True)
class Contexto:
    rng: random.Random
    conocidos: frozenset[str]


def _audio(idioma: str, archivo: str) -> str:
    """Ruta bajo la API; el frontend le antepone apiBase()."""
    return f"/audio/{idioma}/{archivo}"


def _kana(cat: Catalogo, item: str) -> Kana:
    return cat.items[item]


def _distractores(cat: Catalogo, item: str, ctx: Contexto, n: int = 3) -> list[str]:
    """Primero las confusiones que ya viste, después lo demás que ya viste; nunca
    un kana que suene igual (お/を)."""
    k = _kana(cat, item)

    def vale(otro: str) -> bool:
        return otro != item and otro in ctx.conocidos and _kana(cat, otro).sonido != k.sonido

    primero = [f"ja:kana:{c}" for c in k.confusiones if vale(f"ja:kana:{c}")]
    resto = sorted(
        o for o in ctx.conocidos if o.startswith("ja:kana:") and vale(o) and o not in primero
    )
    ctx.rng.shuffle(resto)
    return (primero + resto)[:n]


def eleccion(cat: Catalogo, act: Actividad, ctx: Contexto) -> dict:
    item = act.items[0]
    k = _kana(cat, item)
    opciones = [item, *_distractores(cat, item, ctx)]
    ctx.rng.shuffle(opciones)
    if act.faceta == "reconocer":
        return {
            "item": item,
            "faceta": "reconocer",
            "pregunta": {"texto": k.kana, "lang": "ja", "audio": None},
            "opciones": [
                {"item": o, "texto": _kana(cat, o).romaji, "lang": None} for o in opciones
            ],
            "correcta": item,
        }
    return {
        "item": item,
        "faceta": "oir",
        "pregunta": {"texto": None, "lang": "ja", "audio": _audio("ja", k.audio)},
        "opciones": [{"item": o, "texto": _kana(cat, o).kana, "lang": "ja"} for o in opciones],
        "correcta": item,
    }


def trazo(cat: Catalogo, act: Actividad, ctx: Contexto) -> dict:
    item = act.items[0]
    k = _kana(cat, item)
    return {
        "item": item,
        "kana": k.kana,
        "romaji": k.romaji,
        "audio": _audio("ja", k.audio),
        "trazos": list(k.trazos),
        "mnemotecnia": k.mnemotecnia,
    }


def emparejar(cat: Catalogo, act: Actividad, ctx: Contexto) -> dict:
    pares = [
        {"item": i, "izquierda": _kana(cat, i).kana, "derecha": _kana(cat, i).romaji}
        for i in act.items
    ]
    ctx.rng.shuffle(pares)
    # La faceta viaja en el contenido: en alemán (plan 2) el tablero ejercita el género.
    return {
        "pares": pares,
        "segundos": TABLERO_SEGUNDOS,
        "lang_izquierda": "ja",
        "faceta": act.faceta,
    }


GENERADORES: dict[str, Callable[[Catalogo, Actividad, Contexto], dict]] = {
    "eleccion": eleccion,
    "trazo": trazo,
    "emparejar": emparejar,
}


def generar(cat: Catalogo, act: Actividad, ctx: Contexto) -> dict:
    return GENERADORES[act.dinamica](cat, act, ctx)
