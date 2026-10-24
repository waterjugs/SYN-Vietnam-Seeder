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

# Used when config.process_name is blank: any HLL build.
DEFAULT_PROCESS_PATTERN = re.compile(r"^HLL.*-Win64-Shipping\.exe$", re.IGNORECASE)
EPIC_MANIFEST = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / (
    r"Epic\UnrealEngineLauncher\LauncherInstalled.dat"
)


def detect_epic_app_name(manifest: Path = EPIC_MANIFEST) -> str:
    """Finds HLL Vietnam's Epic AppName from the launcher's install list."""
    try:
        installs = json.loads(manifest.read_text(encoding="utf-8-sig"))["InstallationList"]
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
        self._warned_focus = False

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

    def unlocked(self) -> bool:
        from . import winapi

        return winapi.desktop_unlocked()

    def window(self) -> int | None:
        from . import winapi

        proc = self.process()
        return winapi.main_window(proc.pid) if proc else None

    def rect(self) -> tuple[int, int, int, int] | None:
        """Where the game is drawn on screen: (left, top, width, height)."""
        from . import winapi

        hwnd = self.window()
        return winapi.client_rect(hwnd) if hwnd else None

    def launch_uri(self) -> str:
        if self.config.launcher == "epic":
            app = self.config.epic_app_name or detect_epic_app_name()
            if not app:
                raise RuntimeError("Couldn't find HLL Vietnam in the Epic launcher")
            return f"com.epicgames.launcher://apps/{app}?action=launch&silent=true"
        return f"steam://rungameid/{self.config.steam_app_id}"

    def launch(self, timeout: float | None = None) -> bool:
        """Starts the game and waits for its window. Returns False on timeout."""
        uri = self.launch_uri()
        log.info("Launching the game via %s", uri)
        os.startfile(uri)  # type: ignore[attr-defined]  # Windows only
        timeout = self.config.launch_timeout if timeout is None else timeout
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.window():
                return True
            time.sleep(2)
        names = sorted({p.info["name"] for p in psutil.process_iter(["name"])
                        if (p.info["name"] or "").lower().startswith("hll")})
        log.error("The game window didn't appear within %ss (HLL processes running: %s)",
                  timeout, ", ".join(names) or "none")
        return False

    def focus(self) -> bool:
        """Brings the game to the front. True if it is the foreground window,
        so keys and clicks will land in it."""
        from . import winapi

        hwnd = self.window()
        if not hwnd:
            return False
        if winapi.bring_to_front(hwnd):
            self._warned_focus = False
            return True
        if not self._warned_focus:
            log.warning("Couldn't bring the game to the front; holding input until it is")
            self._warned_focus = True
        return False

    def close(self, linger: float = 0) -> None:
        """Ends the game. With ``linger``, keeps watching that long for a
        late start (Steam can take minutes to launch after an update)."""
        deadline = time.monotonic() + linger
        while True:
            proc = self.process()
            if proc:
                self._end(proc)
            if time.monotonic() >= deadline:
                return
            time.sleep(5)

    def _end(self, proc: psutil.Process) -> None:
        log.info("Closing the game")
        try:
            proc.terminate()
            proc.wait(timeout=30)
        except psutil.TimeoutExpired:
            proc.kill()
        except psutil.NoSuchProcess:
            pass
        except psutil.AccessDenied:
            log.error("Can't close the game: it's running as administrator. Close it yourself, "
                      "and don't run Steam as administrator.")
