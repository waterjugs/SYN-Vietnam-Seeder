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
                in_server = _get_in(config, game, screen, status.weaker_side(), clock)
                if not in_server:
                    game.close()
                    clock.sleep(15)
                    continue

            clock.sleep(config.poll_seconds)
            if not game.running():
                log.warning("The game closed or crashed; restarting")
                in_server = False
                continue

            status = fetch(config.crcon_url) or status
            log.info("Players: %s/%s", status.player_count, config.seeded_threshold)
            if status.player_count >= config.seeded_threshold:
                return Outcome.SEEDED

            game.focus()
            in_server = _keep_in(config, screen, status.weaker_side(), clock)
            if in_server and clock.monotonic() - last_nudge >= config.anti_afk_seconds:
                flow.nudge(screen)
                last_nudge = clock.monotonic()
        return Outcome.TIMED_OUT
    finally:
        game.close()


def _get_in(config, game, screen, side: str, clock: Clock) -> bool:
    if not game.running() and not game.launch():
        return False
    game.focus()
    return flow.join_server(screen, config, clock) and flow.deploy(screen, side, config, clock)


def _keep_in(config, screen, side: str, clock: Clock) -> bool:
    """Handles kicks, new maps and deaths. Returns False if we're out."""
    hit = screen.find_any(["menu_play", flow.TEAM_TEMPLATE[side], *flow.DEPLOY_STAGES])
    if hit is None:
        return True
    if hit[0] == "menu_play":
        log.info("Back at the main menu (kicked or disconnected); rejoining")
        return flow.join_server(screen, config, clock) and flow.deploy(screen, side, config, clock)
    log.info("On a deploy screen (new map or redeploy)")
    flow.deploy(screen, side, config, clock, first_timeout=10)
    return True
