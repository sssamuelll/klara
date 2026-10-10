"""Un catálogo japonés de juguete en disco: seis kana en dos lecciones.

Incluye お y を, que suenan igual («o»), para probar que `oír` nunca los pone
juntos. Los trazos son rectas: aquí no se evalúa la escritura."""

from __future__ import annotations

import copy
import json
from pathlib import Path


def _k(kana: str, romaji: str, *, sonido: str | None = None, confusiones=(), trazos=2) -> dict:
    return {
        "kana": kana,
        "romaji": romaji,
        "sonido": sonido or romaji,
        "confusiones": list(confusiones),
        "trazos": [f"M{10 + 10 * i},20 L{20 + 10 * i},90" for i in range(trazos)],
        "audio": f"{romaji}.mp3",
        "mnemotecnia": f"Suena «{sonido or romaji}».",
    }


KANA_MINI: list[dict] = [
    _k("あ", "a", confusiones=["お"], trazos=3),
    _k("い", "i"),
    _k("う", "u"),
    _k("え", "e"),
    _k("お", "o", confusiones=["あ"], trazos=3),
    _k("を", "wo", sonido="o", confusiones=["お"], trazos=3),
]

MAPA_MINI: dict = {
    "idioma": "ja",
    "escala": ["かな", "N5"],
    "unidades": [
        {
            "id": "hiragana",
            "titulo": "Hiragana",
            "nivel": "かな",
            "puedo": ["Puedo leer, oír y escribir estos kana."],
            "sabes": {
                "vista": "tabla",
                "filas": [
                    ["ja:kana:あ", "ja:kana:い", "ja:kana:う"],
                    ["ja:kana:え", "ja:kana:お", "ja:kana:を"],
                ],
            },
            "lecciones": [
                {
                    "id": "a",
                    "titulo": "あ い う",
                    "bajada": "la fila de あ",
                    "plantilla": "kana",
                    "items": ["ja:kana:あ", "ja:kana:い", "ja:kana:う"],
                },
                {
                    "id": "e",
                    "titulo": "え お を",
                    "bajada": "え, お y を",
                    "plantilla": "kana",
                    "items": ["ja:kana:え", "ja:kana:お", "ja:kana:を"],
                },
            ],
        }
    ],
}


def mapa_mini() -> dict:
    """Una copia que el test puede cambiar sin tocar la de los demás."""
    return copy.deepcopy(MAPA_MINI)


def kana_mini() -> list[dict]:
    return copy.deepcopy(KANA_MINI)


def escribir_catalogo_mini(
    raiz: Path,
    *,
    kana: list[dict] | None = None,
    mapa: dict | None = None,
    sin_audio: tuple[str, ...] = (),
) -> Path:
    ja = raiz / "ja"
    (ja / "audio").mkdir(parents=True, exist_ok=True)
    kana = KANA_MINI if kana is None else kana
    for k in kana:
        if k["audio"] not in sin_audio:
            (ja / "audio" / k["audio"]).write_bytes(b"ID3")
    (ja / "kana.json").write_text(
        json.dumps({"fuente": "prueba", "kana": kana}, ensure_ascii=False), encoding="utf-8"
    )
    (ja / "mapa.json").write_text(
        json.dumps(MAPA_MINI if mapa is None else mapa, ensure_ascii=False), encoding="utf-8"
    )
    return raiz
