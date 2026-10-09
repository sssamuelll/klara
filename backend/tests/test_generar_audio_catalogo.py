"""El generador de audio (spec §7). Lo que habla con Azure se prueba corriéndolo
(tarea 7); aquí, qué se genera y con qué SSML."""

from klara.scripts.generar_audio_catalogo import pendientes, ssml

KANA = [{"kana": "あ", "audio": "a.mp3"}, {"kana": "い", "audio": "i.mp3"}]


def test_pendientes_son_los_que_no_tienen_archivo(tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"ID3")
    assert [k["kana"] for k in pendientes(KANA, tmp_path, solo=None, forzar=False)] == ["い"]


def test_forzar_los_regenera_todos(tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"ID3")
    assert [k["kana"] for k in pendientes(KANA, tmp_path, solo=None, forzar=True)] == ["あ", "い"]


def test_solo_los_pedidos_aunque_existan(tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"ID3")
    assert [k["kana"] for k in pendientes(KANA, tmp_path, solo={"あ"}, forzar=False)] == ["あ"]


def test_ssml_con_la_voz_y_el_idioma():
    s = ssml("あ", "ja", lento=False)
    assert 'xml:lang="ja-JP"' in s
    assert '<voice name="ja-JP-NanamiNeural">あ</voice>' in s
    assert "<prosody" not in s


def test_ssml_lento():
    assert '<prosody rate="-25%">あ</prosody>' in ssml("あ", "ja", lento=True)
