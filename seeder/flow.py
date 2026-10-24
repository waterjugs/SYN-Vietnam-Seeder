"""In-game navigation: server browser, team pick, deploy.

Every step waits for a template (see templates/README.md) and clicks it, so
changing the menu flow after a game patch is mostly a matter of new images.
"""

from __future__ import annotations

import logging
import time

log = logging.getLogger(__name__)

# Dialogs that can pop up anywhere (news, EULA updates, errors). Clicked away.
POPUPS = ["popup_ok", "popup_continue", "popup_close"]

TEAM_TEMPLATE = {"allies": "team_us", "axis": "team_nva"}
DEPLOY_STAGES = ["role_rifleman", "spawn_hq", "deploy_button"]


class Clock:
    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


def wait_for(screen, names: list[str], timeout: float, clock: Clock, quiet: bool = False):
    """Waits until one of ``names`` is on screen; returns (name, pos) or None."""
    deadline = clock.monotonic() + timeout
    while clock.monotonic() < deadline:
        hit = screen.find_any(names + POPUPS)
        if hit and hit[0] in POPUPS:
            log.info("Dismissing %s", hit[0])
            screen.click(hit[1])
        elif hit:
            return hit
        clock.sleep(1)
    if not quiet:
        log.warning("Timed out after %ss waiting for %s", timeout, ", ".join(names))
    return None


def click_when_visible(screen, name: str, timeout: float, clock: Clock) -> bool:
    hit = wait_for(screen, [name], timeout, clock)
    if hit:
        screen.click(hit[1])
        clock.sleep(1)
    return hit is not None


def join_server(screen, config, clock: Clock) -> bool:
    """From the main menu to the server's loading screen."""
    log.info("Opening the server browser")
    if not click_when_visible(screen, "menu_play", config.launch_timeout, clock):
        return False
    if not click_when_visible(screen, "browser_search", 30, clock):
        return False
    screen.type_text(config.server_search)
    screen.press("enter")
    clock.sleep(2)
    log.info("Selecting %s", config.server_name)
    if not click_when_visible(screen, "server_row", 30, clock):
        return False
    return click_when_visible(screen, "browser_join", 15, clock)


def deploy(screen, side: str, config, clock: Clock, first_timeout: float | None = None) -> bool:
    """Picks ``side`` and clicks through role, spawn and deploy.

    Starts from whichever of those screens is showing, so it also handles a
    new map or a redeploy. Returns True once no deploy screen is left.
    """
    stages = [TEAM_TEMPLATE[side]] + DEPLOY_STAGES
    timeout = config.load_timeout if first_timeout is None else first_timeout
    clicked: set[str] = set()
    for _ in range(10):
        hit = wait_for(screen, stages, timeout, clock, quiet=bool(clicked))
        if hit is None:
            # Nothing to click any more: either deployed, or never got here.
            return bool(clicked)
        name, pos = hit
        if name in clicked and name != "deploy_button":
            # Already clicked this one; move on to a later stage if visible.
            later = [s for s in stages[stages.index(name) + 1:] if s not in clicked]
            hit = screen.find_any(later) if later else None
            if hit:
                name, pos = hit
        log.info("Clicking %s", name)
        screen.click(pos)
        clicked.add(name)
        clock.sleep(2)
        timeout = 5
    log.warning("Still on the deploy screens after several tries")
    return False


def nudge(screen) -> None:
    """Small strafe so the idle kick doesn't trigger."""
    screen.hold("a", 0.3)
    screen.hold("d", 0.3)
