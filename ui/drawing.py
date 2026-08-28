"""Antialiased chrome: draw at 4x, box-filter down so 1px edges stay crisp."""

from __future__ import annotations

import tkinter as tk

from PIL import Image, ImageDraw, ImageFilter, ImageTk

_SCALE = 4


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


def _rgb(widget: tk.Misc, color: str) -> tuple[int, int, int]:
    r, g, b = widget.winfo_rgb(color)
    return (r // 256, g // 256, b // 256)


def _rgba(rgb: tuple[int, int, int], alpha: int = 255) -> tuple[int, int, int, int]:
    return (rgb[0], rgb[1], rgb[2], alpha)


def segmented_tab_image(
    width: int,
    height: int,
    radius: int,
    selected: int,
    *,
    bg: tuple[int, int, int],
    track: tuple[int, int, int],
    active: tuple[int, int, int],
    border: tuple[int, int, int],
    inset: int = 1,
) -> Image.Image:
    scale = _SCALE
    sw, sh = width * scale, height * scale
    img = Image.new("RGBA", (sw, sh), _rgba(bg))
    draw = ImageDraw.Draw(img)

    ox1 = inset * scale
    oy1 = inset * scale
    ox2 = (width - inset) * scale - 1
    oy2 = (height - inset) * scale - 1
    inner_w = width - 2 * inset
    inner_h = height - 2 * inset
    orad = min(radius, inner_w // 2, inner_h // 2) * scale

    draw.rounded_rectangle([ox1, oy1, ox2, oy2], orad, fill=_rgba(border))

    ix1 = ox1 + scale
    iy1 = oy1 + scale
    ix2 = ox2 - scale
    iy2 = oy2 - scale
    irad = max(0, orad - scale)
    draw.rounded_rectangle([ix1, iy1, ix2, iy2], irad, fill=_rgba(track))

    mid = (width // 2) * scale
    pill = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pill)
    if selected == 0:
        pd.rounded_rectangle([ix1, iy1, mid + irad, iy2], irad, fill=_rgba(active))
        clip = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        clip.paste(pill.crop((0, 0, mid, sh)), (0, 0))
        pill = clip
    else:
        pd.rounded_rectangle([mid - irad, iy1, ix2, iy2], irad, fill=_rgba(active))
        clip = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        clip.paste(pill.crop((mid, 0, sw, sh)), (mid, 0))
        pill = clip
    img.alpha_composite(pill)

    return img.convert("RGB").resize((width, height), Image.BOX)


def render_segmented_tab(
    canvas: tk.Canvas,
    width: int,
    height: int,
    radius: int,
    selected: int,
    *,
    bg: str,
    track: str,
    active: str,
    border: str,
    inset: int = 1,
) -> ImageTk.PhotoImage:
    return ImageTk.PhotoImage(
        segmented_tab_image(
            width,
            height,
            radius,
            selected,
            bg=_rgb(canvas, bg),
            track=_rgb(canvas, track),
            active=_rgb(canvas, active),
            border=_rgb(canvas, border),
            inset=inset,
        )
    )
