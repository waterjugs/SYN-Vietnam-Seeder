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
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"
FONTS = HERE / "fonts" / "barlow-condensed"

# "Dawn insertion": a jungle at first light. Keep in step with seeder/window.py.
TREELINE = "#121C17"
UNDERGROWTH = "#1D2A22"
EDGE = "#34463B"
HAZE = "#ECE3D0"
MIST = "#8E9C92"
FIRST_LIGHT = "#F2A443"
PADDY = "#86C17A"

# Header sky, top to horizon
SKY = [(0.00, "#0C1823"), (0.38, "#1F2638"), (0.62, "#4B3546"), (0.80, "#9E5141"), (0.93, "#E28E52"), (1.0, "#F6B666")]
SUN_EDGE = "#F7B862"
SUN_CORE = "#FFE6B0"


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


def radial_glow(width: int, height: int, cx: float, cy: float, radius: float, colour: str, strength: float,
                sx: float = 1.0) -> Image.Image:
    """An RGBA layer: colour with alpha falling off from (cx, cy). sx stretches it sideways."""
    yy, xx = np.mgrid[0:height, 0:width].astype(float)
    d = np.sqrt(((xx - cx) / sx) ** 2 + (yy - cy) ** 2) / radius
    a = np.clip(1 - d, 0, 1) ** 2.2 * strength * 255
    layer = np.zeros((height, width, 4), dtype=np.uint8)
    layer[..., :3] = rgb(colour)
    layer[..., 3] = a.clip(0, 255).astype(np.uint8)
    return Image.fromarray(layer, "RGBA")


# --------------------------------------------------------------------------- jungle
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


def draw_palm(draw, base_x, base_y, height, lean, s, fill, fronds=8, seed=0):
    """A coconut palm: curved trunk and drooping feathered fronds. s = pixels per final pixel."""
    rnd = random.Random(seed)
    crown = (base_x + lean * s, base_y - height * s)
    trunk = _bezier((base_x, base_y), (base_x + lean * 0.15 * s, base_y - height * 0.55 * s), crown)
    _tapered(draw, trunk, 3.4 * s, 1.8 * s, fill)
    for k in range(fronds):
        ang = math.radians(-180 + (k + 0.5) * 180 / fronds + rnd.uniform(-9, 9))
        length = rnd.uniform(15, 21) * s
        droop = rnd.uniform(9, 14) * s * (0.4 + abs(math.cos(ang)))
        end = (crown[0] + math.cos(ang) * length, crown[1] + math.sin(ang) * length * 0.55 + droop)
        mid = (crown[0] + math.cos(ang) * length * 0.55, crown[1] + math.sin(ang) * length * 0.55 - 2 * s)
        spine = _bezier(crown, mid, end, 18)
        _tapered(draw, spine, 2.6 * s, 0.6 * s, fill)
        # leaflets hanging from the spine
        for i in range(3, len(spine) - 1, 2):
            x, y = spine[i]
            ll = (1 - i / len(spine)) * 6.5 * s + 1.5 * s
            draw.line([(x, y), (x + math.cos(ang) * 1.5 * s, y + ll)], fill=fill, width=max(1, int(1.1 * s)))
    draw.ellipse([crown[0] - 2.4 * s, crown[1] - 2.0 * s, crown[0] + 2.4 * s, crown[1] + 2.6 * s], fill=fill)


def draw_jungle(draw, width, base, s, fill, seed, crowns=(5, 16), lift=(3, 13), emergent=4):
    """Jungle canopy silhouette: a union of tree crowns of mixed size along y=base (final px),
    a few tall emergent trees, and leaf clumps roughening the top edge. Solid below base."""
    rnd = random.Random(seed)
    xs = np.arange(-20, width + 20, 0.25)
    top = np.full_like(xs, float(base))
    bumps = []
    x = -20.0
    while x < width + 20:
        w = rnd.uniform(*crowns)
        bumps.append((x, w, rnd.uniform(*lift)))
        x += w * rnd.uniform(0.7, 1.3)
    for _ in range(emergent):
        bumps.append((rnd.uniform(0, width), rnd.uniform(crowns[1], crowns[1] * 1.5), lift[1] * rnd.uniform(1.3, 1.7)))
    for cx, w, h in bumps:
        inside = np.abs(xs - cx) < w
        u = (xs[inside] - cx) / w
        top[inside] = np.minimum(top[inside], base - h * np.sqrt(1 - u * u) ** 0.8)
    pts = [(xx * s, yy * s) for xx, yy in zip(xs, top)]
    draw.polygon(pts + [((width + 20) * s, (base + 400) * s), (-20 * s, (base + 400) * s)], fill=fill)
    for i in range(0, len(xs), 10):
        if rnd.random() < 0.55:
            r = rnd.uniform(1.2, 2.8)
            cx, cy = xs[i] + rnd.uniform(-1, 1), top[i] + r * 0.6
            draw.ellipse([(cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s], fill=fill)


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
HEADER_W, HEADER_H = 480, 156
MARK_X, MARK_Y, MARK_UNIT = 16, 16, 0.8  # the seedling's 64-unit box: stem on the baseline
TITLE_X = 66


def make_header(path: Path, scale: int) -> None:
    """The one bold element: night sky warming to a low sun over jungle and palms, with the seedling
    beside the app's name."""
    S = 4 * scale  # drawn at 4x the output size, then reduced
    W, H = HEADER_W * S, HEADER_H * S
    horizon = 128
    img = gradient(W, H, SKY, 0, horizon * S)
    sun_x, sun_y, sun_r = 364, 110, 46
    img.alpha_composite(radial_glow(W, H, sun_x * S, sun_y * S, 130 * S, "#F09A55", 0.55, sx=2.6))
    img.alpha_composite(radial_glow(W, H, sun_x * S, sun_y * S, 90 * S, "#FFD08A", 0.55))

    # sun disc: pale at the top, deeper amber at the bottom
    sun = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    disc = gradient(2 * sun_r * S, 2 * sun_r * S, [(0, SUN_CORE), (0.75, SUN_EDGE), (1, "#F4A957")])
    mask = Image.new("L", disc.size, 0)
    ImageDraw.Draw(mask).ellipse([0, 0, disc.size[0] - 1, disc.size[1] - 1], fill=255)
    sun.paste(disc, ((sun_x - sun_r) * S, (sun_y - sun_r) * S), mask)
    img.alpha_composite(sun)

    # far ridge, warmed by the haze
    far = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_jungle(ImageDraw.Draw(far), HEADER_W, 136, S, rgba("#6A3B3B"), seed=7, crowns=(8, 30), lift=(2, 14),
                emergent=2)
    img.alpha_composite(far.filter(ImageFilter.GaussianBlur(0.4 * S)))
    # valley mist between the ridge and the near trees
    mist = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(mist).rectangle([0, 134 * S, W, 146 * S], fill=rgba("#C7826A", 120))
    img.alpha_composite(mist.filter(ImageFilter.GaussianBlur(4 * S)))

    # near jungle: canopy and palms in the window's own body colour, so the scene runs into the window
    near = ImageDraw.Draw(img)
    draw_jungle(near, HEADER_W, 152, S, rgba(TREELINE), seed=3, crowns=(6, 18), lift=(5, 17), emergent=5)
    for (bx, h, lean, seed) in ((52, 52, -7, 1), (72, 38, 6, 2), (436, 56, 8, 4), (458, 40, -5, 5), (226, 30, 4, 6)):
        draw_palm(near, bx * S, 146 * S, h, lean, S, rgba(TREELINE), seed=seed)

    # the seedling and the wordmark
    draw_sprout(near, MARK_X * S, MARK_Y * S, MARK_UNIT * S)
    title = ImageFont.truetype(str(FONTS / "barlow-condensed-latin-600-normal.woff2"), 36 * S)
    near.text((TITLE_X * S, 26 * S), "SYN Vietnam Seeder", font=title, fill=rgba(HAZE))

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
    """18 x 18 box, plus 8 px of air on the right so the label does not touch it."""
    S = 8 * scale
    box = 18
    img = Image.new("RGBA", ((box + 8) * S, box * S), (0, 0, 0, 0))
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
                            fill=rgba("#8E9C92" if hover else "#5C7064"))
        d.rounded_rectangle([int(2.5 * S), int(2.5 * S), int((box - 2.5) * S) - 1, int((box - 2.5) * S) - 1],
                            radius=2 * S, fill=rgba(UNDERGROWTH))
    return img.resize(((box + 8) * scale, box * scale), Image.LANCZOS)


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
        "btn": box(32, 32, 5, UNDERGROWTH, border=EDGE),
        "btn-hover": box(32, 32, 5, "#26362C", border="#526A5A"),
        "btn-pressed": box(32, 32, 5, "#16211B", border="#526A5A"),
        "btn-focus": box(32, 32, 5, UNDERGROWTH, border="#B88A4A", bw=1.5),
        "btn-disabled": box(32, 32, 5, TREELINE, border="#26342C"),
        # Steam / Epic
        "chip": box(32, 30, 4, TREELINE, border=EDGE),
        "chip-hover": box(32, 30, 4, "#1F2C24", border="#526A5A"),
        "chip-on": box(32, 30, 4, "#3A2F1D", border=FIRST_LIGHT, bw=1.5),
        "chip-focus": box(32, 30, 4, TREELINE, border="#B88A4A", bw=1.5),
        "chip-on-focus": box(32, 30, 4, "#3A2F1D", border="#FFE3B3", bw=1.5),
        # time pickers
        "field": box(32, 30, 4, UNDERGROWTH, border=EDGE),
        "field-hover": box(32, 30, 4, "#22312A", border="#526A5A"),
        "field-focus": box(32, 30, 4, UNDERGROWTH, border="#B88A4A", bw=1.5),
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
TILE_TOP = "#131D29"
TILE_MID = "#33293D"
TILE_LOW = "#8E4A3D"


def icon_image(size: int) -> Image.Image:
    """The app icon at one size: the seedling in front of a rising sun on a dusk tile. From 48 px a
    strip of jungle runs along the horizon; at 32 px and below the seedling is drawn fatter."""
    S = 16 if size <= 64 else 4
    N = size * S
    u = N / 64
    tile = gradient(N, N, [(0, TILE_TOP), (0.5, TILE_MID), (0.82, TILE_LOW), (1, "#C0603F")])
    cx, cy, r = 32 * u, 50 * u, 19 * u
    tile.alpha_composite(radial_glow(N, N, cx, cy, 40 * u, "#F7A55A", 0.6, sx=1.4))
    disc = gradient(N, N, [(0, SUN_CORE), (1, SUN_EDGE)], cy - r, cy + r)
    dmask = Image.new("L", (N, N), 0)
    ImageDraw.Draw(dmask).ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    tile.paste(disc, (0, 0), dmask)
    d = ImageDraw.Draw(tile)
    if size >= 48:
        draw_jungle(d, 64, 57, u, rgba(TREELINE), seed=11, crowns=(4, 9), lift=(2, 6), emergent=0)
    d.ellipse([6 * u, 53 * u, 58 * u, 76 * u], fill=rgba(TREELINE))
    draw_sprout(d, 0, 0, u, bold=size <= 32, outline=rgba(TREELINE))
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
