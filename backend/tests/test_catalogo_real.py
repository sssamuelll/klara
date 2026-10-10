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


def test_las_lecciones_y_la_tabla_siguen_el_inventario():
    # El cargador solo mira un sentido (lo que nombran existe): aquí, que no falte ni sobre nada.
    cat = cargar_catalogo()
    inventario = [k for k in cat.items if k.startswith("ja:kana:")]
    lecciones = [i for lec in cat.lecciones_de("ja") for i in lec.leccion.items]
    tabla = [c for u in cat.mapas["ja"].unidades for fila in u.sabes.filas or () for c in fila if c]
    assert lecciones == inventario
    assert tabla == inventario


def test_cada_kana_con_sus_trazos_y_su_audio():
    cat = cargar_catalogo()
    for clave, k in cat.items.items():
        if clave.startswith("ja:kana:"):
            assert len(k.trazos) == TRAZOS_ESPERADOS[k.kana], k.kana
            audio = cat.audio_path("ja", k.audio)
            assert audio.stat().st_size > 1000, k.kana
            # Una cabecera ID3 o, sin ella, la sincronía de un frame MP3 (11 bits a 1).
            cabecera = audio.read_bytes()[:3]
            sincronia = cabecera[0] == 0xFF and cabecera[1] & 0xE0 == 0xE0
            assert cabecera == b"ID3" or sincronia, k.audio


def test_o_y_wo_suenan_igual_y_se_escriben_distinto():
    cat = cargar_catalogo()
    assert cat.items["ja:kana:お"].sonido == cat.items["ja:kana:を"].sonido == "o"
    assert cat.items["ja:kana:を"].romaji == "wo"
