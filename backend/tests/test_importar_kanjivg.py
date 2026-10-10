"""Trazos de KanjiVG → kana.json (spec §7): se leen como datos y se cuentan."""

from klara.scripts.importar_kanjivg import TRAZOS_ESPERADOS, aplicar_trazos, codigo, trazos_de_svg

HIRAGANA = (
    "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"
)

SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="109" height="109" viewBox="0 0 109 109">
<g id="kvg:StrokePaths_03042" style="fill:none;stroke:#000000;stroke-width:3;">
<g id="kvg:03042" kvg:element="あ">
  <path id="kvg:03042-s2" kvg:type="㇕" d="M51.27,18.88c0.75,1.26,0.98,2.62,0.62,4.32"/>
  <path id="kvg:03042-s1" kvg:type="㇐" d="M31.01,33.21c0.83,0.79,3.07,1.36,4.68,1.25"/>
  <path id="kvg:03042-s3" kvg:type="㇒" d="M66.91,46.29c0.45,1.41,0.24,2.82-0.24,4.39"/>
</g>
</g>
<g id="kvg:StrokeNumbers_03042"><text transform="matrix(1 0 0 1 24.5 34.5)">1</text></g>
</svg>"""


def test_la_tabla_tiene_los_46():
    assert set(TRAZOS_ESPERADOS) == set(HIRAGANA)
    assert len(HIRAGANA) == 46
    assert TRAZOS_ESPERADOS["あ"] == 3
    assert TRAZOS_ESPERADOS["ん"] == 1


def test_codigo():
    assert codigo("あ") == "03042"
    assert codigo("ん") == "03093"


def test_trazos_en_orden_y_sin_lo_que_no_es_trazo():
    assert trazos_de_svg(SVG) == [
        "M31.01,33.21c0.83,0.79,3.07,1.36,4.68,1.25",
        "M51.27,18.88c0.75,1.26,0.98,2.62,0.62,4.32",
        "M66.91,46.29c0.45,1.41,0.24,2.82-0.24,4.39",
    ]


def _svg_con(n: int) -> str:
    paths = "".join(f'<path id="kvg:0-s{i}" d="M{i},0 L{i},9"/>' for i in range(1, n + 1))
    return f"<svg>{paths}</svg>"


def test_aplicar_trazos_cuando_cuadran():
    data = {"kana": [{"kana": "あ", "trazos": []}, {"kana": "ん", "trazos": []}]}
    errores = aplicar_trazos(data, lambda k: _svg_con(TRAZOS_ESPERADOS[k]))
    assert errores == []
    assert [len(e["trazos"]) for e in data["kana"]] == [3, 1]


def test_si_no_cuadra_no_toca_nada():
    data = {"kana": [{"kana": "あ", "trazos": []}, {"kana": "ん", "trazos": []}]}
    errores = aplicar_trazos(data, lambda k: _svg_con(2))
    assert errores == [
        "あ: KanjiVG trae 2 trazos y la tabla dice 3",
        "ん: KanjiVG trae 2 trazos y la tabla dice 1",
    ]
    assert all(e["trazos"] == [] for e in data["kana"])


def test_un_solo_kana_que_no_cuadra_frena_a_todos():
    data = {"kana": [{"kana": "あ", "trazos": []}, {"kana": "ん", "trazos": []}]}
    errores = aplicar_trazos(data, lambda k: _svg_con(3 if k == "あ" else 2))  # あ cuadra, ん no
    assert errores == ["ん: KanjiVG trae 2 trazos y la tabla dice 1"]
    assert all(e["trazos"] == [] for e in data["kana"])
