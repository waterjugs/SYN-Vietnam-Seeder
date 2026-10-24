"""The seeding session: launch, join, stay in, leave once the server is full."""

from __future__ import annotations

import enum
import logging

from . import flow
from .flow import Clock

log = logging.getLogger(__name__)


class Outcome(enum.Enum):
    ALREADY_SEEDED = "server was already seeded"
    SEEDED = "server is seeded"
    SERVER_DOWN = "server status unavailable"
    GAME_IN_USE = "game was already running, left it alone"
    GAVE_UP = "couldn't get into the server"
    TIMED_OUT = "hit the time limit"


def _status(fetch, url: str, clock: Clock, tries: int = 3):
    for attempt in range(tries):
        status = fetch(url)
        if status is not None:
            return status
        if attempt < tries - 1:
            clock.sleep(10)
    return None


def seed(config, game, screen, fetch, clock: Clock | None = None) -> Outcome:
    clock = clock or Clock()
    status = _status(fetch, config.crcon_url, clock)
    if status is None:
        return Outcome.SERVER_DOWN
    log.info("%s has %s players (allies %s, axis %s)", config.server_name,
             status.player_count, status.allied, status.axis)
    if status.player_count >= config.seeded_threshold:
        return Outcome.ALREADY_SEEDED
    if game.running():
        # Someone is playing; don't take over their game.
        return Outcome.GAME_IN_USE

    latest = {"status": status}

    def needy_side():
        s = latest["status"]
        return s.weaker_side() if abs(s.allied - s.axis) >= 2 else None

    nav = flow.Navigator(screen, config, clock, needy_side)
    deadline = clock.monotonic() + config.max_minutes * 60
    attempts = 0
    in_server = False
    last_nudge = clock.monotonic()
    try:
        while clock.monotonic() < deadline:
            if not in_server:
                if attempts > config.max_restarts:
                    return Outcome.GAVE_UP
                attempts += 1
                in_server = _get_in(config, game, nav)
                if not in_server:
                    game.close()
                    clock.sleep(15)
                    continue
                last_nudge = clock.monotonic()

            clock.sleep(config.poll_seconds)
            if not game.running():
                log.warning("The game closed or crashed; restarting")
                in_server = False
                continue

            latest["status"] = fetch(config.crcon_url) or latest["status"]
            count = latest["status"].player_count
            log.info("Players: %s/%s", count, config.seeded_threshold)
            if count >= config.seeded_threshold:
                return Outcome.SEEDED

            game.focus()
            if flow.current_screen(screen) is not None:
                # Kicked to the menu, new map, or died: walk back in.
                log.info("Not in game any more; getting back in")
                in_server = nav.get_in(config.load_timeout)
            elif clock.monotonic() - last_nudge >= config.anti_afk_seconds:
                flow.nudge(screen)
                last_nudge = clock.monotonic()
        return Outcome.TIMED_OUT
    finally:
        game.close()


def _get_in(config, game, nav) -> bool:
    if not game.running() and not game.launch():
        return False
    game.focus()
    return nav.get_in(config.launch_timeout + config.load_timeout)
