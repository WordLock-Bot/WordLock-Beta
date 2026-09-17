"""Generate WordLock PWA app icons (PNG) with a shield/rounded look."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "dashboard" / "public"


def rounded_rect(size: int, radius: int, color: tuple[int, int, int]) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=color)
    return img


def draw_shield(base: Image.Image, size: int) -> Image.Image:
    d = ImageDraw.Draw(base)
    cx = size / 2
    # Shield path (approximate with polygon) in white
    top = int(size * 0.18)
    mid = int(size * 0.52)
    bottom = int(size * 0.82)
    half = int(size * 0.32)
    d.polygon(
        [
            (cx - half, top),
            (cx + half, top),
            (cx + half, mid),
            (cx, bottom),
            (cx - half, mid),
        ],
        fill=(255, 255, 255, 255),
    )
    # Inner 'S' like bar
    d.rounded_rectangle(
        [cx - half * 0.45, int(size * 0.4), cx + half * 0.45, int(size * 0.52)],
        radius=max(2, int(size * 0.03)),
        fill=(88, 101, 242, 255),
    )
    return base


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        base = rounded_rect(size, int(size * 0.2), (88, 101, 242))
        icon = draw_shield(base, size)
        icon.save(OUT / f"icon-{size}.png")
        print(f"wrote {OUT / f'icon-{size}.png'}")


if __name__ == "__main__":
    main()
