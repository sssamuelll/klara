"""Importa los trazos de los kana desde KanjiVG (CC BY-SA 3.0) a `mapas/ja/kana.json`.

Corre una vez al preparar el contenido (spec §7):
1. Baja un SVG por kana del repo de KanjiVG.
2. Saca los `d` de sus trazos, en orden.
3. Compara el número de trazos con la tabla estándar.

Si un solo kana no cuadra, no escribe nada. Lo descargado es dato, no código:
solo se lee con expresiones regulares.

    uv run python -m klara.scripts.importar_kanjivg [--ref master]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from collections.abc import Callable
from pathlib import Path

KANJIVG_RAW = "https://raw.githubusercontent.com/KanjiVG/kanjivg/{ref}/kanji/{codigo}.svg"
KANA_JSON = Path(__file__).resolve().parents[1] / "mapas" / "ja" / "kana.json"

# Los trazos de los 46 hiragana básicos, según KanjiVG.
TRAZOS_ESPERADOS: dict[str, int] = {
    "あ": 3, "い": 2, "う": 2, "え": 2, "お": 3,
    "か": 3, "き": 4, "く": 1, "け": 3, "こ": 2,
    "さ": 3, "し": 1, "す": 2, "せ": 3, "そ": 1,
    "た": 4, "ち": 2, "つ": 1, "て": 1, "と": 2,
    "な": 4, "に": 3, "ぬ": 2, "ね": 2, "の": 1,
    "は": 3, "ひ": 1, "ふ": 4, "へ": 1, "ほ": 4,
    "ま": 3, "み": 2, "む": 3, "め": 2, "も": 3,
    "や": 3, "ゆ": 2, "よ": 2,
    "ら": 2, "り": 2, "る": 1, "れ": 2, "ろ": 1,
    "わ": 2, "を": 3, "ん": 1,
}  # fmt: skip

_PATH = re.compile(r"<path\b[^>]*>")
_ID = re.compile(r'\bid="kvg:[0-9a-f]+-s(\d+)"')
_D = re.compile(r'\bd="([^"]+)"')


def codigo(kana: str) -> str:
    return f"{ord(kana):05x}"


def trazos_de_svg(svg: str) -> list[str]:
    """Los `d` de los trazos, en el orden de KanjiVG (s1, s2…). Los <path> sin id
    de trazo y los <text> de los números se ignoran."""
    trazos: list[tuple[int, str]] = []
    for tag in _PATH.findall(svg):
        m_id, m_d = _ID.search(tag), _D.search(tag)
        if m_id and m_d:
            trazos.append((int(m_id.group(1)), m_d.group(1)))
    return [d for _, d in sorted(trazos)]


def aplicar_trazos(data: dict, bajar: Callable[[str], str]) -> list[str]:
    """Pone en cada kana de `data` los trazos de KanjiVG. Devuelve los errores; si
    hay alguno, no toca `data`."""
    nuevos: dict[str, list[str]] = {}
    errores: list[str] = []
    for entrada in data["kana"]:
        k = entrada["kana"]
        trazos = trazos_de_svg(bajar(k))
        esperados = TRAZOS_ESPERADOS.get(k)
        if esperados is None:
            errores.append(f"{k}: no está en la tabla de trazos")
        elif len(trazos) != esperados:
            errores.append(f"{k}: KanjiVG trae {len(trazos)} trazos y la tabla dice {esperados}")
        nuevos[k] = trazos
    if not errores:
        for entrada in data["kana"]:
            entrada["trazos"] = nuevos[entrada["kana"]]
    return errores


def _bajar(ref: str) -> Callable[[str], str]:
    def bajar(kana: str) -> str:
        url = KANJIVG_RAW.format(ref=ref, codigo=codigo(kana))
        with urllib.request.urlopen(url, timeout=20) as r:
            return r.read().decode("utf-8")

    return bajar


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Trazos de KanjiVG → mapas/ja/kana.json")
    p.add_argument("--ref", default="master", help="rama o tag de KanjiVG (por defecto: master)")
    args = p.parse_args(argv)

    data = json.loads(KANA_JSON.read_text(encoding="utf-8"))
    errores = aplicar_trazos(data, _bajar(args.ref))
    if errores:
        print("No se escribió nada:\n  " + "\n  ".join(errores), file=sys.stderr)
        return 1
    data["fuente"] = f"KanjiVG {args.ref} (CC BY-SA 3.0, Ulrich Apel y colaboradores)"
    KANA_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(data['kana'])} kana con trazos en {KANA_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
