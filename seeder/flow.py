"""In-game navigation for HLL Vietnam, as of build v1.7 (Oct 2026).

What joining looks like in this version:

  splash ("press any button") -> main menu (ENLIST) -> server browser
  (search, JOIN on the server's row) -> Units (the game picks your team;
  SWITCH TEAM is available) -> Edit Roles (F confirms) -> Deployment
  (F deploys at the selected HQ) -> in game.

Admin messages pop up with a "[Y] YES" button, and Esc opens a game menu.
Each tick looks at the screen, works out which of these it is, and does the
one thing that moves it forward. So the same code handles a fresh launch,
a kick back to the main menu, a new map and a death.
"""

from __future__ import annotations

import logging
import time
from typing import Callable

log = logging.getLogger(__name__)

# Screens in the order they're checked. Overlays come first.
SCREENS = [
    "admin_yes",
    "game_menu_leave",
    "deploy_button",
    "roles_confirm",
    "switch_team",
    "server_row",
    "browser_search",
    "menu_enlist",
]

# Parts of the Units screen (fractions of the screen, 16:9 layout).
INFANTRY_COLUMN = (0.29, 0.10, 0.53, 0.95)
INFANTRY_CREATE = (0.29, 0.10, 0.53, 0.22)
FACTION_BADGE = (0.0, 0.75, 0.12, 0.95)


class Clock:
    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


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
    game's pick.
    """

    def __init__(self, screen, config, clock: Clock, side: Callable[[], str | None]):
        self.screen = screen
        self.config = config
        self.clock = clock
        self.side = side
        self.switched_team = False

    def get_in(self, timeout: float) -> bool:
        """Returns True once deployed, False if it didn't get there in time."""
        deadline = self.clock.monotonic() + timeout
        seen_menu = False
        deployed = False
        quiet_ticks = 0
        last = None
        while self.clock.monotonic() < deadline:
            name = current_screen(self.screen)
            if name is None:
                if deployed:
                    quiet_ticks += 1
                    if quiet_ticks >= 3:
                        log.info("Deployed")
                        return True
                elif not seen_menu:
                    # Splash or "press any button"; harmless on loading screens.
                    self.screen.press("space")
                self.clock.sleep(2)
                continue
            seen_menu = True
            quiet_ticks = 0
            if name != last:
                log.info("On screen: %s", name)
                last = name
            if name == "deploy_button":
                deployed = True
            getattr(self, "_on_" + name)()
            self.clock.sleep(2)
        log.warning("Couldn't get into the server within %ss", timeout)
        return False

    # One handler per screen in SCREENS.

    def _on_admin_yes(self) -> None:
        self.screen.press("y")

    def _on_game_menu_leave(self) -> None:
        self.screen.press("esc")

    def _on_deploy_button(self) -> None:
        self.screen.press("f")

    def _on_roles_confirm(self) -> None:
        self.screen.press("f")

    def _on_switch_team(self) -> None:
        wanted = self.side()
        on_axis = self.screen.find("faction_nva", FACTION_BADGE) is not None
        current = "axis" if on_axis else "allies"
        if wanted and wanted != current and not self.switched_team:
            log.info("Switching from %s to %s", current, wanted)
            self.switched_team = True
            self.screen.click(self.screen.find("switch_team"))
            return
        squad = self.screen.find("squad_join", INFANTRY_COLUMN)
        if squad:
            log.info("Joining an infantry squad")
            self.screen.click(squad)
            return
        create = self.screen.find("infantry_create", INFANTRY_CREATE)
        if create:
            log.info("No open squad; creating one")
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
        self.clock.sleep(2)

    def _on_menu_enlist(self) -> None:
        self.screen.click(self.screen.find("menu_enlist"))
        self.clock.sleep(3)


def nudge(screen) -> None:
    """Small strafe so the idle kick doesn't trigger."""
    screen.hold("a", 0.3)
    screen.hold("d", 0.3)
