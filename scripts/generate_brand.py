#!/usr/bin/env python3
"""Generate brand assets (original artwork, no third-party logos).

Produces custom_components/airnow_station/brand/{icon,logo,dark_logo}
per the home-assistant/brands spec: icon 256x256 (+@2x 512), logo
landscape (+@2x), dark_* variants for dark backgrounds. HA 2026.3+
serves these via the local brands proxy.

Usage: python3 scripts/generate_brand.py   (requires Pillow)
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "custom_components" / "airnow_station" / "brand"

BLUE = (21, 101, 192, 255)  # station/pin + wordmark accent
SKY = (3, 169, 244, 255)  # air waves
DARK_TEXT = (26, 26, 46, 255)
WHITE = (255, 255, 255, 255)

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Verdana Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_glyph(size: int) -> Image.Image:
    """Map-pin over three air-wave arcs, on a rounded blue tile."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 512  # design at 512

    d.rounded_rectangle(
        [16 * s, 16 * s, 496 * s, 496 * s], radius=96 * s, fill=BLUE
    )

    # Air waves: three horizontal arcs of decreasing width.
    wave_w = int(26 * s)
    for i, (y, x0, x1) in enumerate(
        [(330, 96, 416), (390, 128, 384), (450, 168, 344)]
    ):
        d.line(
            [(x0 * s, y * s), (x1 * s, y * s)],
            fill=(255, 255, 255, 255 - i * 50),
            width=wave_w,
        )

    # Map pin: circle + tapering triangle, with a hollow center.
    cx, cy, r = 256 * s, 170 * s, 86 * s
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WHITE)
    d.polygon(
        [(cx - r * 0.62, cy + r * 0.62), (cx + r * 0.62, cy + r * 0.62), (cx, cy + r * 1.9)],
        fill=WHITE,
    )
    d.ellipse(
        [cx - r * 0.42, cy - r * 0.42, cx + r * 0.42, cy + r * 0.42], fill=SKY
    )
    return img


def draw_logo(height: int, dark: bool) -> Image.Image:
    glyph = draw_glyph(height)
    font = _font(int(height * 0.42))
    text = "AirNow Station"
    probe = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    tw = int(probe.textlength(text, font=font))
    pad = int(height * 0.18)
    img = Image.new("RGBA", (height + pad + tw + pad, height), (0, 0, 0, 0))
    img.paste(glyph, (0, 0), glyph)
    d = ImageDraw.Draw(img)
    d.text(
        (height + pad, height // 2),
        text,
        font=font,
        fill=WHITE if dark else DARK_TEXT,
        anchor="lm",
    )
    return img


def main() -> None:
    BRAND.mkdir(parents=True, exist_ok=True)
    draw_glyph(512).save(BRAND / "icon@2x.png")
    draw_glyph(512).resize((256, 256), Image.LANCZOS).save(BRAND / "icon.png")
    for name, dark in [("logo", False), ("dark_logo", True)]:
        big = draw_logo(256, dark)
        big.save(BRAND / f"{name}@2x.png")
        big.resize((big.width // 2, 128), Image.LANCZOS).save(BRAND / f"{name}.png")
    for f in sorted(BRAND.iterdir()):
        print(f.name, Image.open(f).size)


if __name__ == "__main__":
    main()
