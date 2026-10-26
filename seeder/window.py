"""The window you get by double-clicking SynSeeder.exe."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk

from . import __version__, crcon, instance, schedule
from .config import Config, app_dir
from .game import Game

log = logging.getLogger(__name__)

HOURS = [f"{h:02d}" for h in range(24)]
MINUTES = [f"{m:02d}" for m in range(0, 60, 5)]


def _start_seed_process() -> None:
    program, arguments = schedule.seed_command()
    flags = 0x00000008 | 0x00000200 if os.name == "nt" else 0  # detached, new group
    subprocess.Popen([program, *arguments.split()], creationflags=flags, close_fds=True)


class SetupWindow:
    def __init__(self, config: Config):
        self.config = config
        self.root = tk.Tk()
        self.root.title("SYN Vietnam Seeder")
        self.root.resizable(False, False)
        frame = ttk.Frame(self.root, padding=16)
        frame.grid()

        ttk.Label(frame, text="SYN Vietnam Seeder", font=("Segoe UI", 14, "bold")).grid(columnspan=4, sticky="w")
        self.server = ttk.Label(frame, text="Checking the server...")
        self.server.grid(columnspan=4, sticky="w", pady=(2, 12))

        hour, minute = config.start_time.split(":")
        ttk.Label(frame, text="Seed every day at").grid(row=2, column=0, sticky="w")
        self.hour = ttk.Combobox(frame, values=HOURS, width=3, state="readonly")
        self.hour.set(hour)
        self.hour.grid(row=2, column=1)
        self.minute = ttk.Combobox(frame, values=MINUTES, width=3, state="readonly")
        self.minute.set(minute if minute in MINUTES else "00")
        self.minute.grid(row=2, column=2, sticky="w")

        ttk.Label(frame, text="Game launcher").grid(row=3, column=0, sticky="w", pady=(8, 0))
        self.launcher = tk.StringVar(value=config.launcher)
        ttk.Radiobutton(frame, text="Steam", variable=self.launcher, value="steam").grid(row=3, column=1, pady=(8, 0))
        ttk.Radiobutton(frame, text="Epic", variable=self.launcher, value="epic").grid(row=3, column=2, pady=(8, 0))

        self.enabled = tk.BooleanVar(value=schedule.is_scheduled())
        ttk.Checkbutton(frame, text="Seed automatically", variable=self.enabled).grid(
            row=4, columnspan=4, sticky="w", pady=(8, 0))

        buttons = ttk.Frame(frame)
        buttons.grid(row=5, columnspan=4, pady=(14, 6), sticky="we")
        ttk.Button(buttons, text="Save", command=self.save).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(buttons, text="Seed now", command=self.seed_now).grid(row=0, column=1, padx=6)
        ttk.Button(buttons, text="Stop seeding", command=self.stop).grid(row=0, column=2, padx=6)

        self.status = ttk.Label(frame, text=self._schedule_text(), wraplength=320, foreground="#555")
        self.status.grid(row=6, columnspan=4, sticky="w")
        footer = ttk.Frame(frame)
        footer.grid(row=7, columnspan=4, sticky="we", pady=(10, 0))
        ttk.Label(footer, text=f"v{__version__}  ·  Ctrl+Alt+End stops a run",
                  foreground="#888").grid(row=0, column=0, sticky="w")
        log_link = ttk.Label(footer, text="Open log", foreground="#2a6ebb", cursor="hand2")
        log_link.grid(row=1, column=0, sticky="w")
        log_link.bind("<Button-1>", lambda _: self.open_log())

        threading.Thread(target=self._load_server, daemon=True).start()

    def _schedule_text(self) -> str:
        if schedule.is_scheduled():
            return (f"Seeds every day at {self.config.start_time}. Leave the PC on, signed in and "
                    "unlocked; if it's asleep it runs when it wakes.")
        return "Not scheduled. Tick “Seed automatically” and Save."

    def _load_server(self) -> None:
        status = crcon.fetch(self.config.crcon_url)
        text = (f"Syndicate has {status.player_count}/100 players right now "
                f"(seeded at {self.config.seeded_threshold})." if status else "Couldn't reach the server stats.")
        self.root.after(0, lambda: self.server.config(text=text))

    def save(self) -> None:
        self.config.start_time = f"{self.hour.get()}:{self.minute.get()}"
        self.config.launcher = self.launcher.get()
        self.config.save()
        try:
            if self.enabled.get():
                schedule.schedule(self.config.start_time)
            else:
                schedule.unschedule()
        except (OSError, RuntimeError) as exc:
            log.exception("Scheduling failed")
            self.status.config(text=f"Couldn't set up the schedule: {exc}", foreground="#b00020")
            return
        self.status.config(text="Saved. " + self._schedule_text(), foreground="#555")

    def seed_now(self) -> None:
        if instance.seeding_processes():
            self.status.config(text="Already seeding.")
            return
        self.save()
        _start_seed_process()
        self.status.config(text="Seeding started. The game will open shortly; leave the "
                                "mouse and keyboard alone while it joins.")

    def stop(self) -> None:
        if instance.stop_seeding():
            Game(self.config).close()
            self.status.config(text="Stopped seeding and closed the game.")
        else:
            self.status.config(text="Nothing is seeding right now.")

    def open_log(self) -> None:
        path = app_dir() / "seeder.log"
        if path.exists() and os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]

    def run(self) -> None:
        self.root.mainloop()


def run(config: Config) -> int:
    SetupWindow(config).run()
    return 0


if __name__ == "__main__":
    sys.exit(run(Config.load()))
