"""Image helpers."""

from __future__ import annotations

from PIL import Image, ImageFilter


def _integer_scale(src: int, dst: int) -> bool:
    return src > 0 and abs(dst / src - round(dst / src)) < 1e-6


def fit_image(
    image: Image.Image,
    width: int,
    height: int,
    *,
    fill: tuple[int, int, int] = (0, 0, 0),
) -> Image.Image:
    """Scale `image` to fit a fixed box without changing the box size."""
    if width <= 0 or height <= 0:
        return Image.new("RGB", (1, 1), fill)
    src = image.convert("RGB")
    scale = min(width / max(src.width, 1), height / max(src.height, 1))
    new_w = max(1, round(src.width * scale))
    new_h = max(1, round(src.height * scale))
    if (new_w, new_h) != (src.width, src.height):
        nearest = _integer_scale(src.width, new_w) and _integer_scale(src.height, new_h)
        if nearest:
            src = src.resize((new_w, new_h), Image.Resampling.NEAREST)
        else:
            src = src.resize((new_w, new_h), Image.Resampling.LANCZOS)
            src = src.filter(ImageFilter.UnsharpMask(radius=0.6, percent=80, threshold=2))
    canvas = Image.new("RGB", (width, height), fill)
    canvas.paste(src, ((width - new_w) // 2, (height - new_h) // 2))
    return canvas
