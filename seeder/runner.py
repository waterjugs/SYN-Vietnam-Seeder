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
    LOCKED = "PC is locked; seeding needs you signed in and unlocked"
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
    if not game.unlocked():
        return Outcome.LOCKED

    latest = {"status": status}

    def needy_side():
        s = latest["status"]
        return s.weaker_side() if abs(s.allied - s.axis) >= 2 else None

    nav = flow.Navigator(screen, config, clock, needy_side, focus=game.focus, alive=game.running,
                         pick=lambda: latest["status"].weaker_side())
    deadline = clock.monotonic() + config.max_minutes * 60
    attempts = 0
    in_server = False
    last_nudge = clock.monotonic()
    outcome = None
    try:
        while True:
            remaining = deadline - clock.monotonic()
            if not in_server:
                if remaining < config.launch_timeout + config.load_timeout:
                    outcome = Outcome.TIMED_OUT
                    return outcome
                if attempts > config.max_restarts:
                    outcome = Outcome.GAVE_UP
                    return outcome
                attempts += 1
                in_server = _get_in(config, game, nav, remaining)
                if not in_server:
                    game.close()
                    clock.sleep(15)
                    continue
                last_nudge = clock.monotonic()
            if remaining <= 0:
                outcome = Outcome.TIMED_OUT
                return outcome

            clock.sleep(config.poll_seconds)
            if not game.running():
                log.warning("The game closed or crashed; restarting")
                in_server = False
                continue

            latest["status"] = fetch(config.crcon_url) or latest["status"]
            count = latest["status"].player_count
            log.info("Players: %s/%s", count, config.seeded_threshold)
            if count >= config.seeded_threshold:
                outcome = Outcome.SEEDED
                return outcome

            if not game.focus():
                continue  # someone else has the screen; send nothing
            name = flow.current_screen(screen)
            if name in flow.OVERLAYS:
                nav.handle(name)
            elif name is not None:
                # Kicked to the menu, new map, or died: walk back in.
                log.info("Not in game any more; getting back in")
                in_server = nav.get_in(min(config.load_timeout, max(remaining, 1)))
            elif clock.monotonic() - last_nudge >= config.anti_afk_seconds:
                flow.nudge(screen)
                last_nudge = clock.monotonic()
    finally:
        # Steam can start the game minutes late (e.g. after an update), so
        # after a failed launch keep watching for it a little longer.
        game.close(linger=90 if outcome is Outcome.GAVE_UP else 0)


def _get_in(config, game, nav, remaining: float) -> bool:
    fresh = not game.running()
    if fresh and not game.launch(min(config.launch_timeout, remaining)):
        return False
    return nav.get_in(min(config.launch_timeout + config.load_timeout, remaining), fresh_launch=fresh)
