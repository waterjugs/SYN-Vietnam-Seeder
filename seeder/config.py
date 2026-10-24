"""Settings, stored as JSON next to the log in %APPDATA%\\SynSeeder."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

APP_NAME = "SynSeeder"


def app_dir() -> Path:
    base = os.environ.get("APPDATA") or Path.home() / ".config"
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class Config:
    # Server to seed
    server_name: str = "Syndicate | Competitive Server"
    server_search: str = "syndicate"  # lowercase: typed key by key
    crcon_url: str = "https://syn-stats-nam.radicalgamingstats.com/api/get_public_info"
    seeded_threshold: int = 80

    # How the game is started: "steam" or "epic"
    launcher: str = "steam"
    steam_app_id: int = 3079210
    epic_app_name: str = ""  # found automatically when empty
    process_name: str = "HLLVietnam-Win64-Shipping.exe"

    # Daily start time (24h, local time) used by the scheduled task
    start_time: str = "07:00"

    # Timings, in seconds unless noted
    poll_seconds: int = 30
    anti_afk_seconds: int = 60
    launch_timeout: int = 300
    load_timeout: int = 240
    max_restarts: int = 3
    max_minutes: int = 240

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        path = path or app_dir() / "config.json"
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self, path: Path | None = None) -> Path:
        path = path or app_dir() / "config.json"
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return path
