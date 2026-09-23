"""
TradeCore uygulama simgesi üreticisi.

Pillow ile her çözünürlükte OLED siyah zemin + zümrüt yükselen grafik + 'TC'
çizer; ardından Windows .ico çoklu-görüntü başlığını elle yazar
(16 / 32 / 48 / 64 / 128 / 256).

Çalıştırma:
  server\\.venv\\Scripts\\python.exe tools\\create_app_icon.py
"""

from __future__ import annotations

import io
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "app.ico"

BG = (9, 9, 11, 255)
EMERALD = (52, 211, 153, 255)
EMERALD_DIM = (16, 185, 129, 180)
GRID = (39, 39, 42, 255)


def render_size(size: int) -> Image.Image:
    """Tek kare terminal ikonu üretir (RGBA)."""
    img = Image.new("RGBA", (size, size), BG)
    draw = ImageDraw.Draw(img)

    margin = max(1, size // 32)
    draw.rectangle(
        [margin, margin, size - margin - 1, size - margin - 1],
        outline=GRID,
        width=max(1, size // 64),
    )

    points = [
        (0.18, 0.72),
        (0.30, 0.62),
        (0.42, 0.68),
        (0.54, 0.48),
        (0.66, 0.42),
        (0.78, 0.28),
        (0.88, 0.22),
    ]
    xy = [(int(x * size), int(y * size)) for x, y in points]
    line_w = max(2, size // 28)
    draw.line(xy, fill=EMERALD, width=line_w, joint="curve")

    tip = xy[-1]
    arrow = max(3, size // 18)
    draw.polygon(
        [
            (tip[0], tip[1] - arrow),
            (tip[0] - arrow // 2, tip[1] + arrow // 3),
            (tip[0] + arrow // 2, tip[1] + arrow // 3),
        ],
        fill=EMERALD,
    )

    try:
        font = ImageFont.truetype("arialbd.ttf", max(10, size // 5))
    except OSError:
        font = ImageFont.load_default()

    text = "TC"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (size - tw) // 2
    ty = int(size * 0.78) - th // 2
    draw.text((tx + 1, ty + 1), text, font=font, fill=EMERALD_DIM)
    draw.text((tx, ty), text, font=font, fill=EMERALD)
    return img


def image_to_png_bytes(img: Image.Image) -> bytes:
    """ICO içinde PNG sıkıştırmalı gömülü görüntü üretir (Vista+)."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def write_multi_ico(path: Path, images: list[Image.Image]) -> None:
    """
    Çoklu çözünürlüklü .ico dosyası yazar.

    ICO yapısı:
    - 6 bayt başlık (reserved, type=1, count)
    - her görüntü için 16 bayt dizin kaydı
    - ardından PNG veri blokları
    """
    payloads = [image_to_png_bytes(img) for img in images]
    count = len(images)
    # Başlık + dizin boyutu
    offset = 6 + (16 * count)
    entries = []
    for img, data in zip(images, payloads):
        w = 0 if img.width >= 256 else img.width
        h = 0 if img.height >= 256 else img.height
        entries.append((w, h, len(data), offset))
        offset += len(data)

    out = io.BytesIO()
    out.write(struct.pack("<HHH", 0, 1, count))
    for w, h, size, off in entries:
        # width, height, palette, reserved, planes, bitcount, bytesinres, offset
        out.write(struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, size, off))
    for data in payloads:
        out.write(data)

    path.write_bytes(out.getvalue())


def main() -> None:
    """app.ico dosyasını proje köküne yazar."""
    sizes = [16, 32, 48, 64, 128, 256]
    frames = [render_size(s) for s in sizes]
    write_multi_ico(OUT, frames)
    print(f"[TradeCore] Ikon yazildi: {OUT} ({OUT.stat().st_size} bayt, {len(frames)} cozunurluk)")


if __name__ == "__main__":
    main()
