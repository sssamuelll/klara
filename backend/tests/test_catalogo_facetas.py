"""Facetas, la nota que pone la dinámica y los metadatos de cada dinámica (spec §1, §3)."""

import pytest

from klara.catalogo.dinamicas import CAP_REPASOS, DINAMICA_DE_REPASO, DINAMICAS, ejercita
from klara.catalogo.facetas import (
    FACETAS_POR_TIPO,
    MODOS,
    faceta_valida,
    idioma_de,
    partes,
    tipo_de,
)
from klara.catalogo.nota import nota
from klara.catalogo.plantillas import PLANTILLAS
from klara.models.enums import ReviewRating


def test_partes_de_una_clave():
    assert partes("ja:kana:あ") == ("ja", "kana", "あ")
    assert tipo_de("de:sustantivo:Frau") == "de:sustantivo"
    assert idioma_de("en:contraste:ɪ-iː") == "en"


@pytest.mark.parametrize("mala", ["", "ja", "ja:kana", "ja::あ", ":kana:あ", "ja:kana:"])
def test_clave_mal_formada(mala):
    with pytest.raises(ValueError):
        partes(mala)


def test_las_facetas_de_la_spec():
    assert FACETAS_POR_TIPO == {
        "ja:kana": frozenset({"reconocer", "oir", "escribir"}),
        "de:sustantivo": frozenset({"genero", "reconocer"}),
        "de:caso": frozenset({"aplicar"}),
        "en:contraste": frozenset({"oir", "pronunciar"}),
    }


def test_faceta_valida():
    assert faceta_valida("ja:kana:あ", "escribir")
    assert not faceta_valida("ja:kana:あ", "genero")
    assert not faceta_valida("xx:raro:a", "oir")
    assert not faceta_valida("mal", "oir")


@pytest.mark.parametrize(
    ("acierto", "pistas", "ms", "esperada"),
    [
        (False, 0, 1000, ReviewRating.AGAIN),
        (False, 3, 1000, ReviewRating.AGAIN),
        (True, 0, 1000, ReviewRating.GOOD),
        (True, 1, 1000, ReviewRating.HARD),
        (True, 0, 9001, ReviewRating.HARD),
        (True, 0, 9000, ReviewRating.GOOD),
    ],
)
def test_nota(acierto, pistas, ms, esperada):
    assert nota(acierto=acierto, pistas=pistas, ms=ms, ms_lento=9000) == esperada


def test_nunca_easy():
    notas = {
        nota(acierto=a, pistas=p, ms=m, ms_lento=5000)
        for a in (True, False)
        for p in (0, 1, 5)
        for m in (0, 4999, 5001)
    }
    assert ReviewRating.EASY not in notas


def test_las_dinamicas_usan_modos_y_facetas_validos():
    assert {"eleccion", "trazo", "emparejar"} <= set(DINAMICAS)
    for nombre, d in DINAMICAS.items():
        assert d.nombre == nombre
        assert d.modos <= set(MODOS)
        assert set(d.segundos) == set(d.modos)
        for tipo, facetas in d.facetas.items():
            assert facetas <= FACETAS_POR_TIPO[tipo]


def test_cada_repaso_usa_una_dinamica_que_lo_comprueba():
    for (tipo, faceta), nombre in DINAMICA_DE_REPASO.items():
        d = DINAMICAS[nombre]
        assert "comprobar" in d.modos
        assert ejercita(d, tipo, faceta)


def test_lo_que_una_plantilla_comprueba_tiene_dinamica_de_repaso():
    # Lo inverso del de arriba: una faceta que se comprueba sin dinámica de repaso
    # nunca vencería en Hoy. Los planes 2 y 3 suman plantillas: cada una, su muestra.
    muestras = {"kana": ("ja:kana:あ", "ja:kana:い")}
    assert set(muestras) == set(PLANTILLAS)
    for nombre, plantilla in PLANTILLAS.items():
        for a in plantilla(muestras[nombre]):
            if a.modo == "comprobar":
                for i in a.items:
                    assert (tipo_de(i), a.faceta) in DINAMICA_DE_REPASO, (nombre, i, a.faceta)


def test_emparejar_solo_practica():
    assert DINAMICAS["emparejar"].modos == frozenset({"practicar"})


def test_el_tope_de_repasos():
    assert CAP_REPASOS == 25
