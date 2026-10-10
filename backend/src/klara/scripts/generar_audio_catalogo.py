"""Genera y valida el audio de los kana (spec §7).

Usa Azure TTS con una voz nativa (ja-JP-NanamiNeural) y guarda el mp3 en
`mapas/ja/audio/`. Antes de guardarlo lo valida con el puntaje de Azure:
- si no pasa, prueba una vez más leyendo despacio;
- si tampoco pasa, igual lo guarda, pero lo lista para que Samuel lo escuche.

Un clip al que Azure no le oye voz cuenta como puntaje 0; los errores de
autenticación, cuota o región detienen la corrida. El mp3 se escribe solo cuando
Azure terminó de sintetizarlo, así que un corte no deja archivos vacíos.

Necesita AZURE_SPEECH_KEY y AZURE_SPEECH_REGION en backend/.env, y nunca las
imprime.

    uv run python -m klara.scripts.generar_audio_catalogo [--solo あ,か] [--forzar]
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from klara.catalogo.cargar import RAIZ_MAPAS
from klara.config import get_settings

VOZ = {"ja": "ja-JP-NanamiNeural"}
LOCALE = {"ja": "ja-JP"}
UMBRAL = 70.0


def _tiene_audio(ruta: Path) -> bool:
    """Un archivo vacío (lo que deja un corte a medias) no cuenta como hecho."""
    return ruta.is_file() and ruta.stat().st_size > 0


def pendientes(
    kana: list[dict], audio_dir: Path, *, solo: set[str] | None, forzar: bool
) -> list[dict]:
    """Los kana que necesitan audio: los pedidos con --solo, todos con --forzar,
    o los que no tienen archivo (o lo tienen vacío)."""
    out = []
    for k in kana:
        if solo is not None:
            if k["kana"] in solo:
                out.append(k)
        elif forzar or not _tiene_audio(audio_dir / k["audio"]):
            out.append(k)
    return out


def ssml(texto: str, idioma: str, *, lento: bool) -> str:
    cuerpo = f'<prosody rate="-25%">{texto}</prosody>' if lento else texto
    return (
        f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{LOCALE[idioma]}">'
        f'<voice name="{VOZ[idioma]}">{cuerpo}</voice></speak>'
    )


def _sintetizar(
    texto: str, idioma: str, destino: Path, formato, *, lento: bool, key: str, region: str
) -> None:
    import azure.cognitiveservices.speech as speechsdk

    cfg = speechsdk.SpeechConfig(subscription=key, region=region)
    cfg.set_speech_synthesis_output_format(formato)
    # audio_config=None deja el audio en memoria. Con AudioOutputConfig(filename=...) el SDK
    # crea el archivo (vacío) al construir el sintetizador, y un corte lo dejaría ahí.
    r = (
        speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=None)
        .speak_ssml_async(ssml(texto, idioma, lento=lento))
        .get()
    )
    if r.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        raise RuntimeError(f"Azure no sintetizó {texto!r}: {r.reason}")
    destino.write_bytes(r.audio_data)


def _puntaje(wav: Path, texto: str, idioma: str, *, key: str, region: str) -> float:
    from klara.pronunciation.azure_client import score_pronunciation

    return score_pronunciation(
        wav, texto, LOCALE[idioma], azure_key=key, azure_region=region
    ).scores.accuracy


def main(argv: list[str] | None = None) -> int:
    # Con la salida redirigida (un pipe) Windows usa cp1252, y ahí los kana no se pueden imprimir.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    import azure.cognitiveservices.speech as speechsdk

    from klara.pronunciation.azure_client import AzureSpeechError

    p = argparse.ArgumentParser(description="Audio de los kana con Azure, validado")
    p.add_argument("--solo", help="kana separados por coma, p. ej. あ,か")
    p.add_argument("--forzar", action="store_true", help="regenera aunque el archivo exista")
    args = p.parse_args(argv)

    s = get_settings()
    if not s.azure_speech_key:
        print("Falta AZURE_SPEECH_KEY en backend/.env", file=sys.stderr)
        return 2
    claves = {"key": s.azure_speech_key, "region": s.azure_speech_region}
    formato = speechsdk.SpeechSynthesisOutputFormat

    ja = RAIZ_MAPAS / "ja"
    audio_dir = ja / "audio"
    audio_dir.mkdir(exist_ok=True)
    data = json.loads((ja / "kana.json").read_text(encoding="utf-8"))
    solo = set(args.solo.split(",")) if args.solo else None

    escuchar: list[str] = []
    for k in pendientes(data["kana"], audio_dir, solo=solo, forzar=args.forzar):
        texto, destino = k["kana"], audio_dir / k["audio"]
        aprobado = None
        for lento in (False, True):
            with tempfile.TemporaryDirectory() as tmp:
                wav = Path(tmp) / "prueba.wav"
                _sintetizar(texto, "ja", wav, formato.Riff16Khz16BitMonoPcm, lento=lento, **claves)
                nota = ""
                try:
                    puntos = _puntaje(wav, texto, "ja", **claves)
                except AzureSpeechError as e:
                    # Sin voz que puntuar es una validación fallida (se reintenta despacio y,
                    # si tampoco, se lista); autenticación, cuota o región no se arreglan solas.
                    if not e.recoverable:
                        raise
                    puntos, nota = 0.0, f" (sin puntaje: {e})"
            print(f"{texto} ({k['romaji']}){' despacio' if lento else ''}: {puntos:.0f}{nota}")
            if puntos >= UMBRAL:
                aprobado = lento
                break
        _sintetizar(
            texto,
            "ja",
            destino,
            formato.Audio24Khz48KBitRateMonoMp3,
            lento=bool(aprobado),
            **claves,
        )
        if aprobado is None:
            # Al momento, no solo al final: si la corrida se corta, la lista no se pierde.
            print(
                f"{texto} ({k['romaji']}): Azure no lo confirmó; escúchalo → {destino.name}",
                flush=True,
            )
            escuchar.append(f"{texto} ({k['romaji']}) → {destino.name}")

    if escuchar:
        print("\nAzure no confirmó estos; escúchalos antes de dar el audio por bueno:")
        print("  " + "\n  ".join(escuchar))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
