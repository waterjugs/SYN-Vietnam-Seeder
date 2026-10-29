"""Entry point for SynSeeder.exe.

  SynSeeder.exe            setup window: start time, launcher, seed now/stop
  SynSeeder.exe --seed     seed now; what the scheduled task runs
  SynSeeder.exe --record   screenshot every few seconds while you click
                           through the menus yourself, to make templates

A release build checks for a newer release before each seeding run and
hands the run over to it (see update.py).
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from . import __version__
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


def run_seed(config: Config, args: list[str], install_to: str | None = None) -> int:
    """``args`` are this process's arguments, passed on if a new version takes over.
    ``install_to`` is set when this process is that new version."""
    import threading

    from . import instance, update

    if not instance.claim():
        log.info("Another seeding run is already going; exiting")
        return 0
    log.info("SynSeeder v%s", __version__)
    try:
        if install_to:
            update.install(Path(install_to))
        elif update.update_and_hand_over(config, args):
            return 0
    except Exception:  # an update going wrong mustn't stop today's seeding
        log.exception("Updating failed; carrying on with this version")

    from . import crcon, runner, winapi
    from .flow import Clock, Stopped
    from .game import Game
    from .screen import Screen

    stop = threading.Event()
    winapi.listen_for_stop_hotkey(stop)
    log.info("Seeding. Press Ctrl+Alt+End to stop.")
    game = Game(config)
    try:
        outcome = runner.seed(config, game, Screen(game.rect), crcon.fetch, Clock(stop))
    except Stopped:
        log.info("Stopped")
        return 0
    except Exception:  # no console in the built exe, so make sure it's logged
        log.exception("Seeding crashed")
        return 2
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
        screen.refresh()  # follows the monitor and warns about black captures
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
    parser.add_argument("--max-minutes", type=int, help="with --seed: end the run after this long (for testing)")
    parser.add_argument("--install-to", help=argparse.SUPPRESS)  # set by update.hand_over()
    argv = sys.argv[1:] if argv is None else argv
    args = parser.parse_args(argv)

    setup_logging()
    try:
        config = Config.load()
    except (OSError, ValueError, TypeError) as exc:
        log.error("Settings file %s is broken (%s); using defaults", app_dir() / "config.json", exc)
        config = Config()
    if args.record:
        return run_record(args.minutes, args.every)
    if args.seed:
        if args.max_minutes:
            config.max_minutes = args.max_minutes
        return run_seed(config, argv, args.install_to)
    from . import window

    return window.run(config)


if __name__ == "__main__":
    sys.exit(main())
