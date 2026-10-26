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

    latest = {"status": status, "at": clock.monotonic()}

    def refresh_status(max_age: float = 0):
        if clock.monotonic() - latest["at"] >= max_age:
            latest["status"] = fetch(config.crcon_url) or latest["status"]
            latest["at"] = clock.monotonic()

    def needy_side():
        s = latest["status"]
        return s.weaker_side() if abs(s.allied - s.axis) >= 2 else None

    def pick():
        # Select Force can come minutes after the last check; use current numbers.
        refresh_status(max_age=30)
        return latest["status"].weaker_side()

    nav = flow.Navigator(screen, config, clock, needy_side, focus=game.focus, alive=game.running, pick=pick)
    deadline = clock.monotonic() + config.max_minutes * 60
    attempts = 0
    in_server = False
    last_nudge = clock.monotonic()
    outcome = None
    try:
        while True:
            remaining = deadline - clock.monotonic()
            if not in_server:
                # The first try always runs (its waits are cut to fit); a retry
                # needs time for a full launch and join.
                if remaining <= 0 or (attempts and remaining < config.launch_timeout + config.load_timeout):
                    outcome = Outcome.TIMED_OUT
                    return outcome
                if attempts > config.max_restarts:
                    outcome = Outcome.GAVE_UP
                    return outcome
                if attempts:
                    refresh_status()
                attempts += 1
                in_server = _get_in(config, game, nav, clock, deadline)
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

            refresh_status()
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
                in_server = nav.get_in(min(config.load_timeout, max(deadline - clock.monotonic(), 1)))
            elif clock.monotonic() - last_nudge >= config.anti_afk_seconds:
                flow.nudge(screen)
                last_nudge = clock.monotonic()
    finally:
        # Steam can start the game minutes late (e.g. after an update), so
        # if it isn't up at the end, keep watching for it a little longer.
        late_start = outcome is Outcome.GAVE_UP or (outcome is Outcome.TIMED_OUT and attempts and not game.running())
        game.close(linger=90 if late_start else 0)


def _get_in(config, game, nav, clock: Clock, deadline: float) -> bool:
    fresh = not game.running()
    if fresh and not game.launch(min(config.launch_timeout, max(deadline - clock.monotonic(), 1))):
        return False
    left = max(deadline - clock.monotonic(), 1)  # what the launch didn't use
    return nav.get_in(min(config.launch_timeout + config.load_timeout, left), fresh_launch=fresh)
