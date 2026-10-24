"""Reads the server's population from a CRCON public info endpoint."""

from __future__ import annotations

import json
import logging
import urllib.request
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ServerStatus:
    name: str
    player_count: int
    allied: int
    axis: int
    time_remaining: float

    def weaker_side(self) -> str:
        """The team to join: the one with fewer players, allies on a tie."""
        return "allies" if self.allied <= self.axis else "axis"


def parse(payload: dict) -> ServerStatus:
    result = payload["result"]
    teams = result.get("player_count_by_team") or {}
    name = result.get("name") or {}
    return ServerStatus(
        name=name.get("name", "") if isinstance(name, dict) else str(name),
        player_count=int(result["player_count"]),
        allied=int(teams.get("allied", 0)),
        axis=int(teams.get("axis", 0)),
        time_remaining=float(result.get("time_remaining") or 0),
    )


def fetch(url: str, timeout: float = 10) -> ServerStatus | None:
    """Returns None when the server or the API can't be reached."""
    request = urllib.request.Request(url, headers={"User-Agent": "SynSeeder"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return parse(json.load(response))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        log.warning("Could not read server status from %s: %s", url, exc)
        return None
