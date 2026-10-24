"""Entry point for SynSeeder.exe.

  SynSeeder.exe            seed now (the setup window comes in a later step)
  SynSeeder.exe --seed     seed now; what the scheduled task runs
  SynSeeder.exe --record   screenshot every few seconds while you click
                           through the menus yourself, to make templates
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime

from .config import Config, app_dir

log = logging.getLogger("seeder")


def setup_logging() -> None:
    handlers: list[logging.Handler] = [logging.FileHandler(app_dir() / "seeder.log", encoding="utf-8")]
    if sys.stdout:
        handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


def run_seed(config: Config) -> int:
    from . import crcon, runner
    from .game import Game
    from .screen import Screen

    outcome = runner.seed(config, Game(config), Screen(), crcon.fetch)
    log.info("Done: %s", outcome.value)
    return 0 if outcome in (runner.Outcome.SEEDED, runner.Outcome.ALREADY_SEEDED) else 1


def run_record(minutes: float, every: float) -> int:
    from .screen import Screen

    out = app_dir() / "screenshots" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True)
    screen = Screen()
    log.info("Recording a screenshot every %ss for %s minutes into %s", every, minutes, out)
    end = time.monotonic() + minutes * 60
    n = 0
    while time.monotonic() < end:
        n += 1
        screen.save_screenshot(out / f"{n:04d}.png")
        time.sleep(every)
    log.info("Saved %s screenshots to %s", n, out)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="SynSeeder")
    parser.add_argument("--seed", action="store_true", help="seed now")
    parser.add_argument("--record", action="store_true", help="record screenshots for templates")
    parser.add_argument("--minutes", type=float, default=10, help="how long --record runs")
    parser.add_argument("--every", type=float, default=3, help="seconds between --record shots")
    args = parser.parse_args(argv)

    setup_logging()
    if args.record:
        return run_record(args.minutes, args.every)
    return run_seed(Config.load())


if __name__ == "__main__":
    sys.exit(main())
