"""Starting, finding, focusing and closing the game process (Windows)."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from urllib.parse import quote, unquote

import psutil

from .config import Config

log = logging.getLogger(__name__)

# Used when config.process_name is blank: any HLL build.
DEFAULT_PROCESS_PATTERN = re.compile(r"^HLL.*-Win64-Shipping\.exe$", re.IGNORECASE)
EPIC_MANIFEST = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / (
    r"Epic\UnrealEngineLauncher\LauncherInstalled.dat"
)
EPIC_APP_NAME = "d7361b7d6fa94097bcadeac4b1f785fb"  # HLL Vietnam's AppName in the Epic store (2026-10-29)
# Seconds without mouse or keyboard use before the seeder pulls the game in
# front of whatever someone was doing; until then it waits for them.
IDLE_BEFORE_TAKEOVER = 15


def detect_epic_app_name(manifest: Path = EPIC_MANIFEST) -> str:
    """Finds HLL Vietnam in the Epic launcher's install list, as namespace:item:app
    like Epic's own shortcuts use, or "" when it isn't installed."""
    try:
        installs = json.loads(manifest.read_text(encoding="utf-8-sig"))["InstallationList"]
    except (OSError, ValueError, KeyError, TypeError):
        return ""
    if not isinstance(installs, list):
        return ""

    def by_folder(entry: dict) -> bool:  # Epic picks the folder name, e.g. Hell_Let_Loose_Vietnam
        folder = re.sub(r"[^a-z0-9]", "", str(entry.get("InstallLocation", "")).lower())
        return "hellletloose" in folder and "vietnam" in folder

    for match in (lambda entry: entry.get("AppName") == EPIC_APP_NAME, by_folder):
        for entry in installs:
            if isinstance(entry, dict) and entry.get("AppName") and match(entry):
                ids = [str(entry.get(key) or "") for key in ("NamespaceId", "ItemId", "AppName")]
                return ":".join(ids) if all(ids) else ids[2]
    return ""


class Game:
    def __init__(self, config: Config):
        self.config = config
        self._focus_wait: str | None = None  # why the game isn't in front, once logged
        self._alt_tapped = False  # force_to_front's Alt tap, used once per wait

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
            # unquote first: a value copied from an Epic shortcut already has %3A in it
            return f"com.epicgames.launcher://apps/{quote(unquote(app.strip()), safe='')}?action=launch&silent=true"
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
        so keys and clicks will land in it.

        If someone is using another window, it waits for them: once the
        mouse and keyboard have been idle for IDLE_BEFORE_TAKEOVER seconds it
        takes the game to the front itself. Meanwhile the game's taskbar
        button flashes to show it's waiting.
        """
        from . import winapi

        hwnd = self.window()
        if not hwnd:
            return False
        winapi.set_input_target(hwnd)  # input is dropped whenever this isn't in front
        if winapi.bring_to_front(hwnd):
            self._in_front()
            return True
        idle = winapi.user_idle_seconds()
        if idle >= IDLE_BEFORE_TAKEOVER:
            if winapi.force_to_front(hwnd, alt_tap=not self._alt_tapped):
                log.info("Brought the game to the front (mouse and keyboard idle for %ss)", round(idle))
                self._in_front()
                return True
            if winapi.in_front(hwnd):
                return False  # ours, but still restoring from minimised: ready on the next try
            self._alt_tapped = True
            wait = "refused"
        else:
            wait = "in use"
        if wait != self._focus_wait:
            if wait == "in use":
                log.warning("Another window is in front and the PC is in use; waiting until the mouse "
                            "and keyboard have been idle for %ss", IDLE_BEFORE_TAKEOVER)
                winapi.flash(hwnd)
            else:
                log.warning("Couldn't bring the game to the front (%s has it); holding input until it is",
                            self._foreground_app())
            self._focus_wait = wait
        return False

    @staticmethod
    def _foreground_app() -> str:
        """Name of the program whose window is in front, for the log."""
        from . import winapi

        pid = winapi.foreground_pid()
        try:
            return psutil.Process(pid).name() if pid else "no window"
        except psutil.Error:
            return "another program"

    def _in_front(self) -> None:
        self._focus_wait = None
        self._alt_tapped = False

    def waiting_for_user(self) -> bool:
        """True while focus() is holding off because someone is using the PC."""
        return self._focus_wait == "in use"

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
