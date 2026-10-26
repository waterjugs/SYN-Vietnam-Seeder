"""Finding buttons on screen by image matching, and clicking/typing into the game.

Templates are PNG crops of game UI taken from 2560x1440 screenshots. Every
frame is shrunk to a 720px-high working copy and lightly blurred, and the
templates are prepared the same way, so one set works at any resolution
(the game scales its UI with screen height). A file named ``name.png`` or
``name.<variant>.png`` belongs to the template ``name``; any variant
matching counts as a hit.

Regions are (left, top, right, bottom) as fractions of the screen.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from .config import app_dir

log = logging.getLogger(__name__)

TEMPLATE_HEIGHT = 1440  # screen height the templates were cropped at
WORK_HEIGHT = 720
BLUR = (3, 3)
MATCH_THRESHOLD = 0.88
# JOIN sits on row backgrounds that vary; real ones score 0.87+, lookalikes < 0.80.
THRESHOLDS = {"browser_join": 0.84}
SCALES = (0.95, 1.0, 1.05)

Region = tuple[float, float, float, float]

REQUIRED_TEMPLATES = {
    "admin_yes", "game_menu_leave", "deploy_button", "roles_confirm", "switch_team", "server_row",
    "browser_search", "browser_refresh", "menu_enlist", "browser_join", "faction_nva", "squad_join",
    "infantry_create", "select_force", "force_us", "force_nva", "create_unit", "create_unit_button",
}


def bundled_templates_dir() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "templates"


def load_templates(*dirs: Path) -> dict[str, list[np.ndarray]]:
    """Later dirs override earlier ones, so players can drop in fixes."""
    templates: dict[str, list[np.ndarray]] = {}
    for directory in dirs:
        if not directory.is_dir():
            continue
        overridden: set[str] = set()
        for file in sorted(directory.glob("*.png")):
            name = file.stem.split(".")[0]
            # imdecode copes with non-ASCII paths (e.g. accented user names); imread doesn't
            image = cv2.imdecode(np.fromfile(str(file), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
            if image is None:
                continue
            if name not in overridden:
                templates[name] = []
                overridden.add(name)
            templates[name].append(image)
    return templates


def prepare_frame(gray: np.ndarray) -> np.ndarray:
    """Shrinks a grayscale screen capture to the working height and blurs it."""
    h, w = gray.shape[:2]
    if h != WORK_HEIGHT:
        gray = cv2.resize(gray, (round(w * WORK_HEIGHT / h), WORK_HEIGHT), interpolation=cv2.INTER_AREA)
    return cv2.GaussianBlur(gray, BLUR, 0)


def prepare_template(image: np.ndarray, scale: float) -> np.ndarray:
    size = (max(1, round(image.shape[1] * scale)), max(1, round(image.shape[0] * scale)))
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
    return cv2.GaussianBlur(cv2.resize(image, size, interpolation=interpolation), BLUR, 0)


def _crop(frame: np.ndarray, region: Region | None) -> tuple[np.ndarray, int, int]:
    if region is None:
        return frame, 0, 0
    h, w = frame.shape[:2]
    x0, y0 = int(region[0] * w), int(region[1] * h)
    x1, y1 = int(region[2] * w), int(region[3] * h)
    return frame[y0:y1, x0:x1], x0, y0


def match_all(
    frame: np.ndarray,
    needles: list[np.ndarray],
    region: Region | None = None,
    threshold: float = MATCH_THRESHOLD,
) -> list[tuple[int, int, float]]:
    """Every match of any prepared needle in a prepared frame, best first.

    Returns centres in frame coordinates with their scores. Overlapping hits
    are merged so each on-screen button is reported once.
    """
    area, ox, oy = _crop(frame, region)
    hits: list[tuple[int, int, float]] = []
    for needle in needles:
        nh, nw = needle.shape[:2]
        if nh > area.shape[0] or nw > area.shape[1]:
            continue
        result = cv2.matchTemplate(area, needle, cv2.TM_CCOEFF_NORMED)
        ys, xs = np.where(result >= threshold)
        for x, y in zip(xs, ys):
            hits.append((ox + int(x) + nw // 2, oy + int(y) + nh // 2, float(result[y, x]), nw, nh))
    hits.sort(key=lambda hit: -hit[2])
    kept: list[tuple[int, int, float, int, int]] = []
    for hit in hits:
        if all(abs(hit[0] - k[0]) > k[3] // 2 or abs(hit[1] - k[1]) > k[4] // 2 for k in kept):
            kept.append(hit)
    return [(x, y, score) for x, y, score, _, _ in kept]


class Vision:
    """Template lookups against the latest frame. No capture or input, so it
    also runs on saved screenshots (see tests)."""

    def __init__(self, raw_templates: dict[str, list[np.ndarray]]) -> None:
        scale = WORK_HEIGHT / TEMPLATE_HEIGHT
        self.templates = {
            name: [prepare_template(img, scale * s) for img in images for s in SCALES]
            for name, images in raw_templates.items()
        }
        self._frame: np.ndarray | None = None
        self._origin = (0, 0)
        self._factor = 1.0

    def set_frame(self, gray: np.ndarray, left: int = 0, top: int = 0) -> None:
        self._frame = prepare_frame(gray)
        self._origin = (left, top)
        self._factor = gray.shape[0] / WORK_HEIGHT

    def _hits(self, name: str, region: Region | None) -> list[tuple[int, int, float]]:
        needles = self.templates.get(name)
        if not needles:
            log.debug("No template named %s", name)
            return []
        if self._frame is None:
            self.refresh()
        return match_all(self._frame, needles, region, THRESHOLDS.get(name, MATCH_THRESHOLD))

    def _to_screen(self, x: int, y: int) -> tuple[int, int]:
        return (self._origin[0] + round(x * self._factor), self._origin[1] + round(y * self._factor))

    def refresh(self) -> None:
        raise NotImplementedError

    def find(self, name: str, region: Region | None = None) -> tuple[int, int] | None:
        hits = self._hits(name, region)
        return self._to_screen(*hits[0][:2]) if hits else None

    def find_all(self, name: str, region: Region | None = None) -> list[tuple[int, int]]:
        return [self._to_screen(x, y) for x, y, _ in self._hits(name, region)]


class Screen(Vision):
    """The real screen and input. Tests swap this for a fake with the same methods.

    ``rect`` returns where the game is drawn (left, top, width, height), or
    None to fall back to the primary monitor; it's asked on every refresh so
    resolution changes and other monitors are followed.
    """

    def __init__(self, rect: Callable[[], tuple[int, int, int, int] | None] = lambda: None) -> None:
        from . import winapi
        import mss

        winapi.make_dpi_aware()
        raw = load_templates(bundled_templates_dir(), app_dir() / "templates")
        log.info("Loaded templates: %s", ", ".join(sorted(raw)) or "none")
        missing = REQUIRED_TEMPLATES - raw.keys()
        if missing:
            raise RuntimeError(f"Missing button images: {', '.join(sorted(missing))}")
        super().__init__(raw)
        self._win = winapi
        self._mss = mss.mss()
        self._rect = rect
        self._area = self._primary()
        self._black_ticks = 0

    def _primary(self) -> dict:
        monitors = self._mss.monitors[1:]
        return next((m for m in monitors if m["left"] == 0 and m["top"] == 0), monitors[0])

    def refresh(self) -> None:
        """Takes a new screenshot; find/find_all use it until the next refresh."""
        rect = self._rect()
        if rect:
            left, top, width, height = rect
            self._area = {"left": left, "top": top, "width": width, "height": height}
        else:
            self._area = self._primary()
        shot = cv2.cvtColor(np.asarray(self._mss.grab(self._area)), cv2.COLOR_BGRA2GRAY)
        self._black_ticks = self._black_ticks + 1 if shot.max() < 16 else 0
        if self._black_ticks == 10:
            log.warning("Screen captures are coming back black. Set the game's display mode "
                        "to Borderless / Windowed Fullscreen.")
        self.set_frame(shot, self._area["left"], self._area["top"])

    # Acting

    def click(self, pos: tuple[int, int] | None) -> None:
        if pos is None:  # the button went away since the screen was read
            return
        self._win.click_at(*pos)
        time.sleep(0.1)
        # Park the cursor at the edge so hover highlights don't change the next match.
        self._win.move_cursor(self._area["left"] + 5, self._area["top"] + self._area["height"] // 2)

    def type_text(self, text: str) -> None:
        self._win.type_text(text)

    def press(self, key: str) -> None:
        self._win.press(key)

    def hold(self, key: str, seconds: float) -> None:
        self._win.key_down(key)
        time.sleep(seconds)
        self._win.key_up(key)

    def save_screenshot(self, path: Path) -> None:
        # Grabs the area of the last refresh without replacing the frame being matched.
        shot = cv2.cvtColor(np.asarray(self._mss.grab(self._area)), cv2.COLOR_BGRA2BGR)
        ok, data = cv2.imencode(".png", shot)
        if ok:
            data.tofile(str(path))
