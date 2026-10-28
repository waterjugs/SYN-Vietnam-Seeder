"""Draws the setup window's images and the app icon into assets/.

    pip install pillow
    python tools/make_assets.py

Writes assets/*.png at 100% scaling, assets/2x/*.png for high-DPI screens
(the window resizes those for 125%, 150% and so on) and assets/synseeder.ico.
Only needed after changing the look; the built exe just loads the files.
The wordmark font is Barlow Condensed (SIL OFL 1.1, see
tools/fonts/barlow-condensed/LICENSE).
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"
FONTS = HERE / "fonts" / "barlow-condensed"

# Keep in step with seeder/window.py.
NIGHT = "#0C1823"
TWILIGHT = "#151A27"
SLATE = "#1F2335"
EDGE = "#363A52"
HAZE = "#ECE3D0"
MIST = "#9C98B0"
FIRST_LIGHT = "#F2A443"
PADDY = "#86C17A"

# Night sky warming to dusk, behind the header and the icon; EMBER glows along the bottom
DUSK = [(0.0, NIGHT), (0.45, "#1A2233"), (0.8, "#352B3E"), (1.0, "#4B3546")]
EMBER = "#9E5141"


def rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgba(h: str, a: int = 255) -> tuple[int, int, int, int]:
    return (*rgb(h), a)


def gradient(width: int, height: int, stops, y0: float = 0.0, y1: float | None = None) -> Image.Image:
    """Vertical gradient through (position, colour) stops between rows y0 and y1."""
    y1 = height if y1 is None else y1
    t = np.clip((np.arange(height) - y0) / max(1.0, (y1 - y0)), 0, 1)
    pos = np.array([s[0] for s in stops])
    cols = np.array([rgb(s[1]) for s in stops], dtype=float)
    rows = np.stack([np.interp(t, pos, cols[:, c]) for c in range(3)], axis=1)
    arr = np.repeat(rows[:, None, :], width, axis=1)
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGB").convert("RGBA")


# --------------------------------------------------------------------------- curves
def _bezier(p0, p1, p2, n=24):
    return [((1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * p1[0] + u * u * p2[0],
             (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * p1[1] + u * u * p2[1]) for u in (i / n for i in range(n + 1))]


def _tapered(draw, pts, w0, w1, fill):
    """Polygon along a centreline whose width goes from w0 to w1."""
    left, right = [], []
    n = len(pts)
    for i, (x, y) in enumerate(pts):
        a = pts[max(0, i - 1)]
        b = pts[min(n - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy) or 1
        nx, ny = -dy / ln, dx / ln
        w = (w0 + (w1 - w0) * i / (n - 1)) / 2
        left.append((x + nx * w, y + ny * w))
        right.append((x - nx * w, y - ny * w))
    draw.polygon(left + right[::-1], fill=fill)


# --------------------------------------------------------------------------- the seedling
SPROUT_GREEN = "#7FCB5A"
SPROUT_VEIN = "#4E9A3A"


def _leaf(draw, base, tip, width, bend, fill, vein=None, vein_width=1):
    """Almond-shaped leaf from base to tip (pixels); bend curves the whole leaf sideways."""
    (bx, by), (tx, ty) = base, tip
    length = math.hypot(tx - bx, ty - by)
    nx, ny = -(ty - by) / length, (tx - bx) / length
    mx, my = (bx + tx) / 2 + nx * bend, (by + ty) / 2 + ny * bend
    draw.polygon(_bezier(base, (mx + nx * width, my + ny * width), tip, 40)
                 + _bezier(tip, (mx - nx * width, my - ny * width), base, 40), fill=fill)
    if vein:
        rib = _bezier(base, (mx + nx * width * 0.15, my + ny * width * 0.15), tip, 40)
        draw.line(rib[:33], fill=vein, width=vein_width, joint="curve")


def draw_sprout(draw, ox, oy, u, bold=False, outline=None) -> None:
    """A two-leaf seedling like the 🌱 emoji in a 64-unit box at (ox, oy), u pixels per unit.
    bold fattens it for small icons; outline draws a dark edge round it first."""
    p = lambda x, y: (ox + x * u, oy + y * u)  # noqa: E731
    stem = [p(x, y) for x, y in _bezier((32, 56), (33.6, 43), (31.6, 30), 40)]
    leaves = [((31.5, 32.5), (8, 19), 10.5 if bold else 9.5, 1.5),
              ((32, 30.5), (55, 11), 11.5 if bold else 10.5, -2.0)]
    edge = 1.3 if bold else 1.0
    for fill, grow in ((outline, edge), (rgba(SPROUT_GREEN), 0)):
        if fill is None:
            continue
        _tapered(draw, stem, ((5.6 if bold else 4.4) + 2 * grow) * u, ((4.0 if bold else 3.0) + 2 * grow) * u, fill)
        for (bx, by), (tx, ty), width, bend in leaves:
            length = math.hypot(tx - bx, ty - by)
            ex, ey = (tx - bx) / length * grow, (ty - by) / length * grow
            vein = rgba(SPROUT_VEIN) if not bold and not grow else None
            _leaf(draw, p(bx - ex, by - ey), p(tx + 1.4 * ex, ty + 1.4 * ey), (width + 1.2 * grow) * u, bend * u,
                  fill, vein, max(1, round(1.1 * u)))


# --------------------------------------------------------------------------- header
HEADER_W, HEADER_H = 480, 92
MARK_Y, MARK_UNIT = 8, 0.8  # the seedling's 64-unit box: stem on the baseline
MARK_GAP = 14               # from the seedling's right leaf to the name
TITLE_Y = 18


def dusk(width: int, height: int, glow: float) -> Image.Image:
    """The dusk wash, with EMBER glowing up from the bottom edge over ``glow`` of the height."""
    img = gradient(width, height, DUSK)
    ember = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(ember).rectangle([0, height * (1 - glow), width, height], fill=rgba(EMBER, 160))
    img.alpha_composite(ember.filter(ImageFilter.GaussianBlur(height * glow / 2)))
    return img


def make_header(path: Path, scale: int) -> None:
    """The seedling and the app's name, centred on the dusk wash, over a line of first light."""
    S = 4 * scale  # drawn at 4x the output size, then reduced
    W, H = HEADER_W * S, HEADER_H * S
    img = dusk(W, H, 0.11)
    d = ImageDraw.Draw(img)
    d.rectangle([0, H - 2 * S, W, H], fill=rgba(FIRST_LIGHT))
    title = ImageFont.truetype(str(FONTS / "barlow-condensed-latin-600-normal.woff2"), 36 * S)
    name = "SYN Vietnam Seeder"
    left, _, right, _ = d.textbbox((0, 0), name, font=title)
    # the seedling's leaves span x 8..55 of its box; centre seedling + gap + name as one group
    mark_w = (55 - 8) * MARK_UNIT * S
    group = mark_w + MARK_GAP * S + (right - left)
    x = (W - group) / 2
    draw_sprout(d, x - 8 * MARK_UNIT * S, MARK_Y * S, MARK_UNIT * S)
    d.text((x + mark_w + MARK_GAP * S - left, TITLE_Y * S), name, font=title, fill=rgba(HAZE))
    img = img.resize((HEADER_W * scale, HEADER_H * scale), Image.LANCZOS).convert("RGB")
    img.save(path)


# --------------------------------------------------------------------------- controls
def rounded(w, h, r, fill, border=None, bw=1.0, inset=0.0, scale=1) -> Image.Image:
    """A w x h antialiased rounded rectangle (r = corner radius), drawn at 4x and reduced."""
    S = 4 * scale
    img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    box = [inset * S, inset * S, (w - inset) * S - 1, (h - inset) * S - 1]
    if border:
        d.rounded_rectangle(box, radius=r * S, fill=rgba(border))
        b = bw * S
        d.rounded_rectangle([box[0] + b, box[1] + b, box[2] - b, box[3] - b], radius=max(0, (r - bw)) * S,
                            fill=rgba(fill) if fill else (0, 0, 0, 0))
    else:
        d.rounded_rectangle(box, radius=r * S, fill=rgba(fill))
    return img.resize((w * scale, h * scale), Image.LANCZOS)


def check_image(on: bool, hover: bool, scale: int) -> Image.Image:
    """18 x 18 box."""
    S = 8 * scale
    box = 18
    img = Image.new("RGBA", (box * S, box * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if on:
        d.rounded_rectangle([S, S, (box - 1) * S - 1, (box - 1) * S - 1], radius=3 * S,
                            fill=rgba("#F7B65E" if hover else FIRST_LIGHT))
        pts = [(5.0 * S, 9.4 * S), (7.9 * S, 12.2 * S), (13.2 * S, 6.2 * S)]
        d.line(pts, fill=rgba("#1A140C"), width=int(2.1 * S), joint="curve")
        for x, y in (pts[0], pts[-1]):
            r = 1.05 * S
            d.ellipse([x - r, y - r, x + r, y + r], fill=rgba("#1A140C"))
    else:
        d.rounded_rectangle([S, S, (box - 1) * S - 1, (box - 1) * S - 1], radius=3 * S,
                            fill=rgba(MIST if hover else "#666A85"))
        d.rounded_rectangle([int(2.5 * S), int(2.5 * S), int((box - 2.5) * S) - 1, int((box - 2.5) * S) - 1],
                            radius=2 * S, fill=rgba(SLATE))
    return img.resize((box * scale, box * scale), Image.LANCZOS)


def chevron(colour: str, scale: int) -> Image.Image:
    """Down chevron for the time pickers: 22 x 16, drawn left of centre to leave a right margin."""
    S = 8 * scale
    img = Image.new("RGBA", (22 * S, 16 * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pts = [(5.5 * S, 6.2 * S), (9.5 * S, 10.2 * S), (13.5 * S, 6.2 * S)]
    d.line(pts, fill=rgba(colour), width=int(1.8 * S), joint="curve")
    for x, y in (pts[0], pts[-1]):
        r = 0.9 * S
        d.ellipse([x - r, y - r, x + r, y + r], fill=rgba(colour))
    return img.resize((22 * scale, 16 * scale), Image.LANCZOS)


def make_widgets(out: Path, scale: int) -> None:
    def box(w, h, r, fill, border=None, bw=1.0):
        return rounded(w, h, r, fill, border=border, bw=bw, scale=scale)

    w = {
        # Save: the one filled button
        "btn-primary": box(32, 32, 5, FIRST_LIGHT),
        "btn-primary-hover": box(32, 32, 5, "#F7B65E"),
        "btn-primary-pressed": box(32, 32, 5, "#D98C2E"),
        "btn-primary-focus": box(32, 32, 5, FIRST_LIGHT, border="#FFE3B3", bw=1.5),
        "btn-primary-disabled": box(32, 32, 5, "#5A4A33"),
        # Seed now, Stop seeding
        "btn": box(32, 32, 5, SLATE, border=EDGE),
        "btn-hover": box(32, 32, 5, "#292E45", border="#555B78"),
        "btn-pressed": box(32, 32, 5, "#121624", border="#555B78"),
        "btn-focus": box(32, 32, 5, SLATE, border="#B88A4A", bw=1.5),
        "btn-disabled": box(32, 32, 5, TWILIGHT, border="#262A3B"),
        # Steam / Epic
        "chip": box(32, 30, 4, TWILIGHT, border=EDGE),
        "chip-hover": box(32, 30, 4, "#1E2234", border="#555B78"),
        "chip-on": box(32, 30, 4, "#3A2F1D", border=FIRST_LIGHT, bw=1.5),
        "chip-focus": box(32, 30, 4, TWILIGHT, border="#B88A4A", bw=1.5),
        "chip-on-focus": box(32, 30, 4, "#3A2F1D", border="#FFE3B3", bw=1.5),
        # time pickers
        "field": box(32, 30, 4, SLATE, border=EDGE),
        "field-hover": box(32, 30, 4, "#262A3F", border="#555B78"),
        "field-focus": box(32, 30, 4, SLATE, border="#B88A4A", bw=1.5),
        "chevron": chevron(HAZE, scale),
        # Seed automatically
        "check-off": check_image(False, False, scale),
        "check-off-hover": check_image(False, True, scale),
        "check-on": check_image(True, False, scale),
        "check-on-hover": check_image(True, True, scale),
    }
    for name, img in w.items():
        img.save(out / f"{name}.png")


# --------------------------------------------------------------------------- icon
ICON_SIZES = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]


def icon_image(size: int) -> Image.Image:
    """The app icon at one size: the seedling on a dusk tile, drawn fatter and edged at 32 px and below."""
    S = 16 if size <= 64 else 4
    N = size * S
    u = N / 64 * 0.98
    tile = dusk(N, N, 0.18)
    ox, oy = N / 2 - 31.5 * u, N / 2 - 33.5 * u  # the seedling spans x 8..55, y 11..56 of its box
    draw_sprout(ImageDraw.Draw(tile), ox, oy, u, bold=size <= 32, outline=rgba("#0A0E18") if size <= 32 else None)
    mask = Image.new("L", (N, N), 0)
    inset = 0 if size <= 32 else N * 0.03
    ImageDraw.Draw(mask).rounded_rectangle([inset, inset, N - 1 - inset, N - 1 - inset],
                                           radius=N * (0.19 if size <= 32 else 0.22), fill=255)
    out = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    out.paste(tile, (0, 0), mask)
    out = out.resize((size, size), Image.LANCZOS)
    if size <= 48:
        out = out.filter(ImageFilter.UnsharpMask(radius=0.6, percent=50, threshold=0))
    return out


def make_icon() -> None:
    images = {s: icon_image(s) for s in ICON_SIZES}
    images[256].save(ASSETS / "synseeder.ico", sizes=[(s, s) for s in ICON_SIZES],
                     append_images=[images[s] for s in ICON_SIZES if s != 256])
    for s in (16, 32, 48):  # the window icon where .ico files aren't supported (not Windows)
        images[s].save(ASSETS / f"icon-{s}.png")


if __name__ == "__main__":
    for scale, out in ((1, ASSETS), (2, ASSETS / "2x")):
        out.mkdir(parents=True, exist_ok=True)
        make_header(out / "header.png", scale)
        make_widgets(out, scale)
    make_icon()
    print("Wrote", ASSETS)
