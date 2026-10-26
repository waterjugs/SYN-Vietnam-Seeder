"""In-game navigation for HLL Vietnam, as of build v1.7 (Oct 2026).

What joining looks like in this version:

  splash ("press any button") -> main menu (ENLIST) -> server browser
  (search, JOIN on the server's row) -> Select Force (US or NVA; skipped
  when rejoining a server you were just on) -> Units (SWITCH TEAM is
  available; join a squad, or + opens a Create a Unit popup whose CREATE
  UNIT button makes you its squad leader) -> Edit Roles (F confirms) ->
  Deployment (F deploys at the selected HQ) -> in game.

Admin messages pop up with a "[Y] YES" button, and Esc opens a game menu;
both are overlays that can show up in game too. Each tick looks at the
screen, works out which of these it is, and does the one thing that moves
it forward. So the same code handles a fresh launch, a kick back to the
main menu, a new map and a death.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

log = logging.getLogger(__name__)

# Screens in the order they're checked. Overlays come first.
OVERLAYS = ("admin_yes", "game_menu_leave")
SCREENS = [
    *OVERLAYS,
    "deploy_button",
    "roles_confirm",
    "select_force",
    "create_unit",
    "switch_team",
    "server_row",
    "browser_search",
    "browser_refresh",
    "menu_enlist",
]

# Parts of the Units screen (fractions of the game area, 16:9 layout).
INFANTRY_COLUMN = (0.29, 0.10, 0.53, 0.95)
INFANTRY_CREATE = (0.29, 0.10, 0.53, 0.22)
FACTION_BADGE = (0.0, 0.75, 0.12, 0.95)
# The two cards on Select Force.
FORCE_CARDS = {"allies": ("force_us", (0.05, 0.30, 0.50, 0.55)), "axis": ("force_nva", (0.50, 0.30, 0.95, 0.55))}
FORCE_TRIES = 5  # clicks (~10 s) on one card before trying the other, in case it's locked
# The bottom right of the Create a Unit popup, where its CREATE UNIT button is.
CREATE_UNIT_BUTTON = (0.55, 0.60, 0.95, 0.90)

REFRESH_EVERY = 20  # seconds between server list refreshes while our server is missing
STUCK_TICKS = 90  # ~3 minutes on a screen we don't know (a map load takes 1-2) before a screenshot
STUCK_REPEATS = 15  # the same screen this many ticks in a row also gets a screenshot
KEEP_SCREENSHOTS = 20  # newest debug screenshots kept


class Stopped(Exception):
    """The player asked the seeder to stop."""


class Clock:
    def __init__(self, stop: threading.Event | None = None):
        self.stop = stop or threading.Event()

    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        if self.stop.wait(seconds):
            raise Stopped()


def current_screen(screen) -> str | None:
    """Which menu is showing, or None when in game / loading."""
    screen.refresh()
    for name in SCREENS:
        if screen.find(name):
            return name
    return None


class Navigator:
    """Walks from wherever the game is to deployed on the server.

    ``side`` is called whenever a team decision comes up and returns the
    team that needs players ("allies" or "axis"), or None to keep the
    game's pick. ``pick`` returns the team to choose on Select Force (the
    smaller one). ``focus`` brings the game to the front and says whether it
    is; no input is sent while it isn't. ``alive`` says whether the game is
    still running.
    """

    def __init__(self, screen, config, clock: Clock, side: Callable[[], str | None],
                 focus: Callable[[], bool] = lambda: True, alive: Callable[[], bool] = lambda: True,
                 pick: Callable[[], str] = lambda: "allies"):
        self.screen = screen
        self.config = config
        self.clock = clock
        self.side = side
        self.pick = pick
        self.focus = focus
        self.alive = alive
        self.switched_team = False
        self._force_tries = 0
        self._force_team: str | None = None
        self._tried: list[tuple[int, int]] = []
        self._last_refresh = float("-inf")

    def get_in(self, timeout: float, fresh_launch: bool = False) -> bool:
        """Returns True once deployed (or back in game), False if that didn't
        happen in time or the game closed.

        ``fresh_launch`` means the game was just started, so a blank screen
        is the splash waiting for a key rather than gameplay.
        """
        deadline = self.clock.monotonic() + timeout
        # One team switch per trip in; a later rejoin may need another.
        self.switched_team = False
        seen: set[str] = set()
        deployed = False
        quiet_ticks = 0
        unknown_ticks = 0
        last, repeats = None, 0
        while self.clock.monotonic() < deadline:
            if not self.alive():
                log.warning("The game closed while getting into the server")
                return False
            if not self.focus():
                self.clock.sleep(2)
                continue
            name = current_screen(self.screen)
            if name is None:
                in_game = deployed or (not fresh_launch and seen <= set(OVERLAYS))
                if in_game:
                    quiet_ticks += 1
                    if quiet_ticks >= 3:
                        log.info("In game")
                        return True
                else:
                    if fresh_launch and not seen - set(OVERLAYS):
                        self.screen.press("space")  # splash / "press any button"
                    unknown_ticks += 1
                    if unknown_ticks == STUCK_TICKS:
                        self._snapshot("unrecognised screen for 3 minutes")
                self.clock.sleep(2)
                continue
            quiet_ticks = unknown_ticks = 0
            repeats = repeats + 1 if name == last else 0
            last = name
            if name not in seen:
                log.info("On screen: %s", name)
            seen.add(name)
            if name not in OVERLAYS:
                deployed = name == "deploy_button"
            if name != "switch_team":
                self._tried.clear()
            if name not in OVERLAYS and name != "select_force":
                self._force_tries, self._force_team = 0, None
            self.handle(name)
            # After acting, so the screenshot can't replace the frame the handler used.
            if repeats == STUCK_REPEATS and name != "browser_refresh":  # waiting on the list is normal
                self._snapshot(f"still on {name} after {STUCK_REPEATS} tries")
            self.clock.sleep(2)
        log.warning("Couldn't get into the server within %ss", round(timeout))
        return False

    def _snapshot(self, why: str) -> None:
        """Saves what's on screen so an unexpected menu can be added later."""
        save = getattr(self.screen, "save_screenshot", None)
        if save is None:
            log.warning("Stuck: %s", why)
            return
        import contextlib
        from datetime import datetime

        from .config import app_dir

        try:
            folder = app_dir() / "debug"
            folder.mkdir(exist_ok=True)
            path = folder / f"{datetime.now():%Y%m%d-%H%M%S}.png"
            save(path)
        except Exception as exc:  # a failed debug screenshot must not end the run
            log.warning("Stuck: %s (screenshot failed: %s)", why, exc)
            return
        log.warning("Stuck: %s. Saved %s", why, path)
        # Names sort oldest first; keep the folder from growing forever.
        for old in sorted(folder.glob("*.png"))[:-KEEP_SCREENSHOTS]:
            with contextlib.suppress(OSError):  # e.g. open in a viewer
                old.unlink()

    def handle(self, name: str) -> None:
        getattr(self, "_on_" + name)()

    # One handler per screen in SCREENS.

    def _on_admin_yes(self) -> None:
        self.screen.click(self.screen.find("admin_yes"))

    def _on_game_menu_leave(self) -> None:
        self.screen.press("esc")

    def _on_deploy_button(self) -> None:
        self.screen.press("f")

    def _on_roles_confirm(self) -> None:
        self.screen.press("f")

    def _on_select_force(self) -> None:
        if self._force_team is None:
            self._force_team = self.pick()  # once per visit, so the choice can't flip mid-way
        team = self._force_team
        other = "axis" if team == "allies" else "allies"
        if (self._force_tries // FORCE_TRIES) % 2:
            # Still here after several clicks: that card may be locked. Take
            # turns between the two so a slow screen still ends up on ours.
            team, other = other, team
        card = self.screen.find(*FORCE_CARDS[team])
        if card is None:
            team, card = other, self.screen.find(*FORCE_CARDS[other])
        if card is None:
            log.warning("Couldn't find the US or NVA card on Select Force")
            return
        if self._force_tries % FORCE_TRIES == 0:
            log.info("Picking %s", "US" if team == "allies" else "NVA")
        self._force_tries += 1
        self.switched_team = True  # chosen deliberately; don't switch again on Units
        self.screen.click(card)

    def _on_create_unit(self) -> None:
        button = self.screen.find("create_unit_button", CREATE_UNIT_BUTTON)
        if button:
            log.info("Creating the unit")
            self.screen.click(button)

    def _on_switch_team(self) -> None:
        wanted = self.side()
        on_axis = self.screen.find("faction_nva", FACTION_BADGE) is not None
        current = "axis" if on_axis else "allies"
        if wanted and wanted != current and not self.switched_team:
            log.info("Switching from %s to %s", current, wanted)
            self.switched_team = True
            self.screen.click(self.screen.find("switch_team"))
            return
        # Join the first infantry squad not tried yet on this visit; a full
        # or locked one leaves us here, so the next tick tries another.
        for squad in sorted(self.screen.find_all("squad_join", INFANTRY_COLUMN), key=lambda p: p[1]):
            if all(abs(squad[0] - t[0]) > 15 or abs(squad[1] - t[1]) > 15 for t in self._tried):
                log.info("Joining an infantry squad")
                self._tried.append(squad)
                self.screen.click(squad)
                return
        create = self.screen.find("infantry_create", INFANTRY_CREATE)
        if create:
            log.info("No open squad; creating one")
            self._tried.clear()
            self.screen.click(create)

    def _on_server_row(self) -> None:
        row = self.screen.find("server_row")
        joins = self.screen.find_all("browser_join")
        if row and joins:
            # The JOIN button on the same row as the server's name.
            self.screen.click(min(joins, key=lambda pos: abs(pos[1] - row[1])))

    def _on_browser_search(self) -> None:
        self.screen.click(self.screen.find("browser_search"))
        self.clock.sleep(0.5)
        self.screen.type_text(self.config.server_search)
        self.screen.press("enter")
        self._last_refresh = self.clock.monotonic()
        self.clock.sleep(2)

    def _on_browser_refresh(self) -> None:
        # Searched, but our server isn't listed (yet): it may be restarting.
        if self.clock.monotonic() - self._last_refresh >= REFRESH_EVERY:
            log.info("Server not in the list; refreshing")
            self.screen.press("r")
            self._last_refresh = self.clock.monotonic()

    def _on_menu_enlist(self) -> None:
        self.screen.click(self.screen.find("menu_enlist"))
        self.clock.sleep(3)


def nudge(screen) -> None:
    """Small strafe so the idle kick doesn't trigger."""
    screen.hold("a", 0.3)
    screen.hold("d", 0.3)
