"""Cargar y validar el catálogo (spec §2.1): si algo no cuadra, CatalogoInvalido
con TODOS los errores."""

import pytest

from klara.catalogo.cargar import CatalogoInvalido, cargar_catalogo
from tests.catalogo_mini import escribir_catalogo_mini, kana_mini, mapa_mini


def _errores(tmp_path, **kw) -> list[str]:
    with pytest.raises(CatalogoInvalido) as e:
        cargar_catalogo(escribir_catalogo_mini(tmp_path / "mapas", **kw))
    return e.value.errores


def _con_leccion(actividades: list[dict]) -> dict:
    m = mapa_mini()
    m["unidades"][0]["lecciones"].append(
        {"id": "x", "titulo": "x", "bajada": "x", "actividades": actividades}
    )
    return m


def _act(dinamica, modo, faceta, items=("ja:kana:あ",)) -> dict:
    return {"dinamica": dinamica, "modo": modo, "items": list(items), "faceta": faceta}


def test_carga_el_catalogo_mini(tmp_path):
    cat = cargar_catalogo(escribir_catalogo_mini(tmp_path / "mapas"))
    assert list(cat.mapas) == ["ja"]
    assert len(cat.items) == 6
    assert list(cat.lecciones) == ["ja/hiragana/a", "ja/hiragana/e"]
    acts = cat.lecciones["ja/hiragana/a"].leccion.actividades
    # 3 kana: trazo presentar+practicar (6), elección reconocer+oír (6), tablero (1),
    # prueba: trazo, reconocer y oír (9).
    assert len(acts) == 22
    assert [(a.dinamica, a.modo) for a in acts[:2]] == [
        ("trazo", "presentar"),
        ("trazo", "practicar"),
    ]
    assert cat.audio_path("ja", "a.mp3").is_file()
    assert [lec.id for lec in cat.lecciones_de("ja")] == ["ja/hiragana/a", "ja/hiragana/e"]


def test_item_que_no_existe(tmp_path):
    m = mapa_mini()
    m["unidades"][0]["lecciones"][0]["items"].append("ja:kana:か")
    assert any("ja:kana:か" in e and "no existe" in e for e in _errores(tmp_path, mapa=m))


def test_faceta_que_no_es_del_tipo(tmp_path):
    m = _con_leccion([_act("trazo", "practicar", "genero"), _act("trazo", "comprobar", "genero")])
    assert any("'genero' no es faceta de ja:kana" in e for e in _errores(tmp_path, mapa=m))


def test_modo_que_la_dinamica_no_soporta(tmp_path):
    m = _con_leccion([_act("emparejar", "comprobar", "reconocer", ("ja:kana:あ", "ja:kana:い"))])
    assert any("emparejar no soporta el modo comprobar" in e for e in _errores(tmp_path, mapa=m))


def test_dinamica_que_no_ejercita_esa_faceta(tmp_path):
    m = _con_leccion(
        [_act("eleccion", "practicar", "escribir"), _act("eleccion", "comprobar", "escribir")]
    )
    assert any("eleccion no ejercita ja:kana × escribir" in e for e in _errores(tmp_path, mapa=m))


def test_dinamica_desconocida(tmp_path):
    m = _con_leccion([_act("dictado", "comprobar", "oir")])
    assert any("dinámica desconocida 'dictado'" in e for e in _errores(tmp_path, mapa=m))


def test_practica_sin_prueba(tmp_path):
    m = _con_leccion([_act("eleccion", "practicar", "reconocer")])
    assert any(
        "practica ja:kana:あ × reconocer y no lo comprueba" in e for e in _errores(tmp_path, mapa=m)
    )


def test_falta_un_audio(tmp_path):
    assert any("falta el audio i.mp3" in e for e in _errores(tmp_path, sin_audio=("i.mp3",)))


def test_kana_sin_trazos(tmp_path):
    kana = kana_mini()
    kana[1]["trazos"] = []
    assert any("い sin trazos" in e for e in _errores(tmp_path, kana=kana))


def test_confusion_fuera_del_inventario(tmp_path):
    kana = kana_mini()
    kana[0]["confusiones"] = ["ぬ"]
    assert any("confunde con ぬ" in e for e in _errores(tmp_path, kana=kana))


def test_plantilla_desconocida(tmp_path):
    m = mapa_mini()
    m["unidades"][0]["lecciones"][0]["plantilla"] = "kanji"
    assert any("plantilla desconocida 'kanji'" in e for e in _errores(tmp_path, mapa=m))


def test_nivel_fuera_de_la_escala(tmp_path):
    m = mapa_mini()
    m["unidades"][0]["nivel"] = "N1"
    assert any("'N1' no está en la escala" in e for e in _errores(tmp_path, mapa=m))


def test_lo_que_sabes_nombra_algo_de_otra_unidad(tmp_path):
    m = mapa_mini()
    m["unidades"][0]["lecciones"][1]["items"].remove("ja:kana:を")
    assert any(
        "nombra ja:kana:を, que no está en la unidad" in e for e in _errores(tmp_path, mapa=m)
    )


def test_leccion_repetida(tmp_path):
    m = mapa_mini()
    m["unidades"][0]["lecciones"][1]["id"] = "a"
    assert any("id de lección repetido" in e for e in _errores(tmp_path, mapa=m))


def test_el_mapa_dice_otro_idioma(tmp_path):
    m = mapa_mini()
    m["idioma"] = "de"
    assert any("dice idioma 'de'" in e for e in _errores(tmp_path, mapa=m))


def test_json_roto(tmp_path):
    raiz = escribir_catalogo_mini(tmp_path / "mapas")
    (raiz / "ja" / "mapa.json").write_text("{ esto no es json", encoding="utf-8")
    with pytest.raises(CatalogoInvalido) as e:
        cargar_catalogo(raiz)
    assert any("mapa.json" in err for err in e.value.errores)


def test_idioma_sin_inventario(tmp_path):
    raiz = escribir_catalogo_mini(tmp_path / "mapas")
    (raiz / "xx").mkdir()
    with pytest.raises(CatalogoInvalido) as e:
        cargar_catalogo(raiz)
    assert any("xx: no hay inventario registrado" in err for err in e.value.errores)


def test_junta_todos_los_errores(tmp_path):
    errores = _errores(tmp_path, sin_audio=("i.mp3", "u.mp3"))
    assert any("i.mp3" in e for e in errores)
    assert any("u.mp3" in e for e in errores)


def test_get_catalogo_usa_klara_mapas_dir(catalogo_mini):
    assert list(catalogo_mini.mapas) == ["ja"]
    assert len(catalogo_mini.items) == 6
