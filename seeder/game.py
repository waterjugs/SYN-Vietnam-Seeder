"""Starting, finding, focusing and closing the game process (Windows)."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path

import psutil

from .config import Config

log = logging.getLogger(__name__)

# The shipping exe for HLL Vietnam isn't confirmed yet, so match any HLL build.
DEFAULT_PROCESS_PATTERN = re.compile(r"^HLL.*-Win64-Shipping\.exe$", re.IGNORECASE)
EPIC_MANIFEST = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / (
    r"Epic\UnrealEngineLauncher\LauncherInstalled.dat"
)


def detect_epic_app_name(manifest: Path = EPIC_MANIFEST) -> str:
    """Finds HLL Vietnam's Epic AppName from the launcher's install list."""
    try:
        installs = json.loads(manifest.read_text(encoding="utf-8"))["InstallationList"]
    except (OSError, ValueError, KeyError):
        return ""
    for entry in installs:
        location = entry.get("InstallLocation", "").lower().replace(" ", "")
        if "hellletloose" in location and "vietnam" in location:
            return entry.get("AppName", "")
    return ""


class Game:
    def __init__(self, config: Config):
        self.config = config

    def _matches(self, name: str) -> bool:
        if self.config.process_name:
            return name.lower() == self.config.process_name.lower()
        return bool(DEFAULT_PROCESS_PATTERN.match(name))

    def process(self) -> psutil.Process | None:
        for proc in psutil.process_iter(["name"]):
            if proc.info["name"] and self._matches(proc.info["name"]):
                return proc
        return None

    def running(self) -> bool:
        return self.process() is not None

    def launch_uri(self) -> str:
        if self.config.launcher == "epic":
            app = self.config.epic_app_name or detect_epic_app_name()
            if not app:
                raise RuntimeError("Couldn't find HLL Vietnam in the Epic launcher")
            return f"com.epicgames.launcher://apps/{app}?action=launch&silent=true"
        return f"steam://rungameid/{self.config.steam_app_id}"

    def launch(self) -> bool:
        """Starts the game and waits for its process. Returns False on timeout."""
        uri = self.launch_uri()
        log.info("Launching the game via %s", uri)
        os.startfile(uri)  # type: ignore[attr-defined]  # Windows only
        deadline = time.monotonic() + self.config.launch_timeout
        while time.monotonic() < deadline:
            proc = self.process()
            if proc:
                if not self.config.process_name:
                    log.info("Game process is %s", proc.name())
                return True
            time.sleep(2)
        log.error("The game didn't start within %ss", self.config.launch_timeout)
        return False

    def focus(self) -> None:
        """Brings the game window to the front so clicks and keys land in it."""
        proc = self.process()
        if proc:
            _focus_pid(proc.pid)

    def close(self) -> None:
        proc = self.process()
        if not proc:
            return
        log.info("Closing the game")
        proc.terminate()
        try:
            proc.wait(timeout=30)
        except psutil.TimeoutExpired:
            proc.kill()


def _focus_pid(pid: int) -> None:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    found: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(callback, 0)
    if found:
        user32.ShowWindow(found[0], 9)  # SW_RESTORE
        user32.SetForegroundWindow(found[0])
