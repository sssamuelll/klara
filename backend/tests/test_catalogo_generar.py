"""El contenido de cada actividad (spec §3.1): sale del catálogo, igual para
lecciones y repasos."""

import random

from klara.catalogo.dinamicas import DINAMICAS
from klara.catalogo.generar import GENERADORES, Contexto, generar
from klara.catalogo.modelo import Actividad


def _ctx(cat, conocidos=None, semilla=1) -> Contexto:
    return Contexto(
        rng=random.Random(semilla),
        conocidos=frozenset(cat.items if conocidos is None else conocidos),
    )


def _act(dinamica, modo, items, faceta) -> Actividad:
    return Actividad(dinamica=dinamica, modo=modo, items=tuple(items), faceta=faceta)


def test_hay_un_generador_por_dinamica():
    assert set(GENERADORES) == set(DINAMICAS)


def test_eleccion_reconocer(catalogo_mini):
    c = generar(
        catalogo_mini,
        _act("eleccion", "practicar", ["ja:kana:あ"], "reconocer"),
        _ctx(catalogo_mini),
    )
    assert c["pregunta"] == {"texto": "あ", "lang": "ja", "audio": None}
    assert c["correcta"] == "ja:kana:あ"
    assert c["faceta"] == "reconocer"
    assert len(c["opciones"]) == 4
    assert {"item": "ja:kana:あ", "texto": "a", "lang": None} in c["opciones"]


def test_la_confusion_va_siempre(catalogo_mini):
    act = _act("eleccion", "practicar", ["ja:kana:あ"], "reconocer")
    for semilla in range(10):
        c = generar(catalogo_mini, act, _ctx(catalogo_mini, semilla=semilla))
        assert "ja:kana:お" in {o["item"] for o in c["opciones"]}


def test_distractores_solo_de_lo_conocido(catalogo_mini):
    conocidos = {"ja:kana:あ", "ja:kana:い", "ja:kana:う"}
    c = generar(
        catalogo_mini,
        _act("eleccion", "practicar", ["ja:kana:あ"], "reconocer"),
        _ctx(catalogo_mini, conocidos),
    )
    assert {o["item"] for o in c["opciones"]} <= conocidos
    assert len(c["opciones"]) == 3  # solo hay dos distractores conocidos


def test_oir_nunca_junta_dos_que_suenan_igual(catalogo_mini):
    act = _act("eleccion", "comprobar", ["ja:kana:を"], "oir")
    for semilla in range(20):
        c = generar(catalogo_mini, act, _ctx(catalogo_mini, semilla=semilla))
        assert "ja:kana:お" not in {o["item"] for o in c["opciones"]}
        assert c["pregunta"] == {"texto": None, "lang": "ja", "audio": "/audio/ja/wo.mp3"}
        assert all(o["lang"] == "ja" for o in c["opciones"])


def test_misma_semilla_mismo_contenido(catalogo_mini):
    act = _act("eleccion", "practicar", ["ja:kana:い"], "reconocer")
    assert generar(catalogo_mini, act, _ctx(catalogo_mini, semilla=7)) == generar(
        catalogo_mini, act, _ctx(catalogo_mini, semilla=7)
    )


def test_trazo(catalogo_mini):
    c = generar(
        catalogo_mini, _act("trazo", "comprobar", ["ja:kana:あ"], "escribir"), _ctx(catalogo_mini)
    )
    assert c["item"] == "ja:kana:あ"
    assert c["kana"] == "あ"
    assert c["romaji"] == "a"
    assert len(c["trazos"]) == 3
    assert c["audio"] == "/audio/ja/a.mp3"
    assert c["mnemotecnia"]


def test_emparejar(catalogo_mini):
    items = ["ja:kana:あ", "ja:kana:い", "ja:kana:う"]
    c = generar(
        catalogo_mini, _act("emparejar", "practicar", items, "reconocer"), _ctx(catalogo_mini)
    )
    assert sorted(p["item"] for p in c["pares"]) == sorted(items)
    assert {p["izquierda"]: p["derecha"] for p in c["pares"]} == {"あ": "a", "い": "i", "う": "u"}
    assert c["segundos"] == 45
    assert c["lang_izquierda"] == "ja"
    assert c["faceta"] == "reconocer"
