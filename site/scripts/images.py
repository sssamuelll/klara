"""Produce hero.webp, og.jpg y las tres capturas en WebP a partir de site/art/.

  python scripts/images.py            # todo
  python scripts/images.py --shots    # solo las capturas (tras scripts/shots.mjs)

Capturas: si art/shots/<nombre>.png no existe, escribe un relleno del tamaño
final en color pizarra para que el build y la revisión no se bloqueen.
"""
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ART, PUB = ROOT / "art", ROOT / "public"
SHOTS = ["today", "read", "speak", "review"]
SHOT_W, SHOT_H = 390, 760          # CSS px; el PNG viene a 2x
FILL = (0x1C, 0x1F, 0x24)          # --nbc-surface de noche


def hero() -> None:
    im = Image.open(ART / "hero.png").convert("RGB")
    w = 2000
    h = round(im.height * w / im.width)
    big = im.resize((w, h), Image.LANCZOS)
    big.save(PUB / "hero.webp", "WEBP", quality=82, method=6)
    # og.jpg: 1200x630, recorte centrado
    ow, oh = 1200, 630
    scale = max(ow / im.width, oh / im.height)
    sw, sh = round(im.width * scale), round(im.height * scale)
    og = im.resize((sw, sh), Image.LANCZOS)
    left, top = (sw - ow) // 2, (sh - oh) // 2
    og.crop((left, top, left + ow, top + oh)).save(PUB / "og.jpg", "JPEG", quality=80, optimize=True, progressive=True)
    print("hero.webp", (PUB / "hero.webp").stat().st_size // 1024, "KB;", "og.jpg", (PUB / "og.jpg").stat().st_size // 1024, "KB")


def shots() -> None:
    (PUB / "shots").mkdir(parents=True, exist_ok=True)
    for name in SHOTS:
        src = ART / "shots" / f"{name}.png"
        out = PUB / "shots" / f"{name}.webp"
        if src.exists():
            im = Image.open(src).convert("RGB")
            # Recorte superior a 390x760 (en px CSS) manteniendo la escala 2x.
            scale = im.width / SHOT_W
            im = im.crop((0, 0, im.width, min(im.height, round(SHOT_H * scale))))
            im = im.resize((SHOT_W * 2, SHOT_H * 2), Image.LANCZOS)
            im.save(out, "WEBP", quality=82, method=6)
            print(name, "real", out.stat().st_size // 1024, "KB")
        elif out.exists():
            # Sin PNG crudo (estan ignorados por git) se conserva la captura ya publicada.
            print(name, "sin PNG; se conserva", out.stat().st_size // 1024, "KB")
        else:
            Image.new("RGB", (SHOT_W * 2, SHOT_H * 2), FILL).save(out, "WEBP", quality=60, method=6)
            print(name, "RELLENO", out.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    if "--shots" not in sys.argv:
        hero()
    shots()
