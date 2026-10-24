"""Finding buttons on screen by image matching, and clicking/typing into the game.

Templates are PNG crops of game buttons taken at 1920x1080. They're scaled to
the player's resolution when matching, so one set works on any 16:9 or
ultrawide screen. A file named ``name.png`` or ``name.<variant>.png`` belongs
to the template ``name``; any variant matching counts as a hit.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from .config import app_dir

log = logging.getLogger(__name__)

REF_HEIGHT = 1080
MATCH_THRESHOLD = 0.82


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
            image = cv2.imread(str(file), cv2.IMREAD_GRAYSCALE)
            if image is None:
                continue
            if name not in overridden:
                templates[name] = []
                overridden.add(name)
            templates[name].append(image)
    return templates


def match_template(
    haystack: np.ndarray,
    needle: np.ndarray,
    scales: list[float],
    threshold: float = MATCH_THRESHOLD,
) -> tuple[int, int, float] | None:
    """Best match of ``needle`` in ``haystack`` (both grayscale) over scales.

    Returns the centre of the match and its score, or None below threshold.
    """
    best: tuple[int, int, float] | None = None
    for scale in scales:
        h, w = needle.shape[:2]
        size = (max(1, round(w * scale)), max(1, round(h * scale)))
        if size[0] > haystack.shape[1] or size[1] > haystack.shape[0]:
            continue
        scaled = cv2.resize(needle, size, interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
        result = cv2.matchTemplate(haystack, scaled, cv2.TM_CCOEFF_NORMED)
        _, score, _, (x, y) = cv2.minMaxLoc(result)
        if score >= threshold and (best is None or score > best[2]):
            best = (x + size[0] // 2, y + size[1] // 2, float(score))
    return best


class Screen:
    """Real screen and input. Tests swap this for a fake with the same methods."""

    def __init__(self) -> None:
        import mss
        import pydirectinput

        self._mss = mss.mss()
        self._input = pydirectinput
        pydirectinput.FAILSAFE = True  # slam the mouse into a corner to abort
        self.templates = load_templates(bundled_templates_dir(), app_dir() / "templates")
        log.info("Loaded templates: %s", ", ".join(sorted(self.templates)) or "none")

    def grab(self) -> np.ndarray:
        monitor = self._mss.monitors[1]
        frame = np.asarray(self._mss.grab(monitor))
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)

    def _scales(self, frame: np.ndarray) -> list[float]:
        s = frame.shape[0] / REF_HEIGHT
        return [s * f for f in (0.9, 0.95, 1.0, 1.05, 1.1)]

    def find(self, name: str, frame: np.ndarray | None = None) -> tuple[int, int] | None:
        variants = self.templates.get(name)
        if not variants:
            log.debug("No template named %s", name)
            return None
        frame = self.grab() if frame is None else frame
        scales = self._scales(frame)
        for needle in variants:
            hit = match_template(frame, needle, scales)
            if hit:
                return hit[0], hit[1]
        return None

    def find_any(self, names: list[str]) -> tuple[str, tuple[int, int]] | None:
        frame = self.grab()
        for name in names:
            pos = self.find(name, frame)
            if pos:
                return name, pos
        return None

    def click(self, pos: tuple[int, int]) -> None:
        self._input.moveTo(*pos)
        time.sleep(0.15)
        self._input.click()

    def type_text(self, text: str) -> None:
        self._input.typewrite(text, interval=0.05)

    def press(self, key: str) -> None:
        self._input.press(key)

    def hold(self, key: str, seconds: float) -> None:
        self._input.keyDown(key)
        time.sleep(seconds)
        self._input.keyUp(key)

    def save_screenshot(self, path: Path) -> None:
        cv2.imwrite(str(path), cv2.cvtColor(np.asarray(self._mss.grab(self._mss.monitors[1])), cv2.COLOR_BGRA2BGR))
