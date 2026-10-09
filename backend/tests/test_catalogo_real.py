"""El catálogo de verdad (backend/src/klara/mapas) carga sin errores (spec §2.1)."""

from klara.catalogo.cargar import cargar_catalogo
from klara.scripts.importar_kanjivg import TRAZOS_ESPERADOS

FILAS = ("a", "ka", "sa", "ta", "na", "ha", "ma", "ya", "ra", "wa")


def test_carga_el_mapa_de_japones():
    cat = cargar_catalogo()
    assert cat.mapas["ja"].escala == ("かな", "N5", "N4", "N3")
    kana = {k.split(":")[2] for k in cat.items if k.startswith("ja:kana:")}
    assert kana == set(TRAZOS_ESPERADOS)
    assert [lec.id for lec in cat.lecciones_de("ja")] == [f"ja/hiragana/{f}" for f in FILAS]


def test_cada_kana_con_sus_trazos_y_su_audio():
    cat = cargar_catalogo()
    for clave, k in cat.items.items():
        if clave.startswith("ja:kana:"):
            assert len(k.trazos) == TRAZOS_ESPERADOS[k.kana], k.kana
            assert cat.audio_path("ja", k.audio).stat().st_size > 1000, k.kana


def test_o_y_wo_suenan_igual_y_se_escriben_distinto():
    cat = cargar_catalogo()
    assert cat.items["ja:kana:お"].sonido == cat.items["ja:kana:を"].sonido == "o"
    assert cat.items["ja:kana:を"].romaji == "wo"
