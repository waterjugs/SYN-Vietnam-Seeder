import os
import shutil
import subprocess
import sys
import tkinter as tk
from pathlib import Path

import pytest

from seeder import crcon, schedule, window
from seeder.config import Config

LOAD_SERVER = window.SetupWindow._load_server  # the fixture swaps it out
ROOT = Path(__file__).resolve().parent.parent

needs_display = pytest.mark.skipif(os.name != "nt" and not os.environ.get("DISPLAY"), reason="no display for Tk")


@pytest.fixture
def calls(monkeypatch, tmp_path):
    """Records what the window asks of the scheduler and the seeder; nothing real happens."""
    if os.name != "nt" and not os.environ.get("DISPLAY"):
        pytest.skip("no display for Tk")
    monkeypatch.setenv("APPDATA", str(tmp_path))  # config.json lands here
    monkeypatch.setattr(window, "_make_dpi_aware", lambda: None)  # once per process; see the last test
    made = []
    monkeypatch.setattr(schedule, "is_scheduled", lambda: True)
    monkeypatch.setattr(schedule, "schedule", lambda start: made.append(("schedule", start)))
    monkeypatch.setattr(schedule, "unschedule", lambda: made.append(("unschedule",)))
    monkeypatch.setattr(window, "_start_seed_process", lambda: made.append(("seed",)))
    monkeypatch.setattr(window.instance, "seeding_processes", lambda: [])
    monkeypatch.setattr(window.SetupWindow, "_load_server", lambda self: None)  # no thread, no network
    monkeypatch.setattr(window.Game, "running", lambda self: False)
    return made


@pytest.fixture
def win(calls):
    w = window.SetupWindow(Config(start_time="06:35", launcher="epic"))
    yield w
    w.root.destroy()


@pytest.mark.parametrize("dpi", [96, 120, 144, 192])  # 100%, 125% and 150% (resized from 2x), 200%
def test_opens_at_any_scaling(calls, monkeypatch, tmp_path, dpi):
    # The exe unpacks its images under the user's own name, e.g. C:\Users\José\AppData\Local\Temp
    assets = tmp_path / "José" / "assets"
    shutil.copytree(window.ASSETS, assets)
    monkeypatch.setattr(window, "ASSETS", assets)
    monkeypatch.setattr(tk.Misc, "winfo_fpixels", lambda self, distance: float(dpi))
    w = window.SetupWindow(Config())
    w.root.update()
    assert w.scale == dpi / 96
    assert w.root.winfo_width() == w._image("header").width() == round(480 * dpi / 96)
    w.root.destroy()


@pytest.mark.skipif(os.name != "nt", reason="the bundled font is only loaded on Windows")
def test_writes_in_the_bundled_inter(win):
    assert win.font_body[0] == win.font_count[0] == "Inter"


def test_shows_settings(win):
    assert (win.hour.get(), win.minute.get(), win.launcher.get()) == ("06", "35", "epic")
    assert win.enabled.get()
    assert win.status.cget("text").startswith("Seeds every day at 06:35.")


def test_clock_says_am_or_pm(win):
    assert win.clock.cget("text") == "6:35 AM"
    for hour, shown in (("00", "12:35 AM"), ("12", "12:35 PM"), ("19", "7:35 PM")):
        win.hour.set(hour)
        win.hour.event_generate("<<ComboboxSelected>>")
        assert win.clock.cget("text") == shown


def test_server_count(win):
    win._show_server(37)
    assert (win.count.cget("text"), win.need.cget("text")) == ("37", "Needs 43 more")
    assert win.count.winfo_manager() == "grid"
    win._show_server(84)
    assert win.need.cget("text") == "Seeded"
    win._show_server(None)
    assert str(win.server.cget("text")) == "Couldn't reach the server stats."
    assert win.count.winfo_manager() == ""  # hidden


@pytest.mark.parametrize("threshold", [0, 80, 100, 150])
def test_threshold_label_stays_on_the_meter(calls, threshold):
    w = window.SetupWindow(Config(seeded_threshold=threshold))
    label = w.meter.find_all()[-1]
    assert w.meter.itemcget(label, "text") == f"Seeded at {threshold}"
    x0, _, x1, _ = w.meter.bbox(label)
    assert 0 <= x0 and x1 <= w.content_width
    w.root.destroy()


def test_load_server_shows_the_count(win, monkeypatch):
    monkeypatch.setattr(crcon, "fetch", lambda url: crcon.ServerStatus("x", 12, 6, 6, 0))
    LOAD_SERVER(win)
    win.root.update()
    assert (win.count.cget("text"), win.need.cget("text")) == ("12", "Needs 68 more")


class FakeFetch:
    """Stands in for the fetch thread: runs at once unless told to keep running."""

    hang = False

    def __init__(self, target, daemon):
        self.target, self.daemon, self.running = target, daemon, False

    def start(self):
        if not FakeFetch.hang:
            self.target()
        self.running = FakeFetch.hang

    def is_alive(self):
        return self.running


@pytest.fixture
def fetches(win, monkeypatch):
    win._fetch.join()  # the window's own first fetch, a no-op here
    loads, timers = [], []
    FakeFetch.hang = False
    monkeypatch.setattr(window.threading, "Thread", FakeFetch)
    monkeypatch.setattr(window.SetupWindow, "_load_server", lambda self: loads.append(1))
    monkeypatch.setattr(win.root, "after", lambda ms, then: timers.append((ms, then)))
    return loads, timers


def test_player_count_keeps_refreshing(win, fetches):
    loads, timers = fetches
    win._refresh_server()
    assert loads == [1] and timers == [(window.SERVER_REFRESH_MS, win._refresh_server)]
    assert win._fetch.daemon  # off the Tk thread, and never keeps the app open
    timers.pop()[1]()  # 30 s later
    assert loads == [1, 1] and len(timers) == 1


def test_slow_fetch_is_not_doubled_up(win, fetches):
    _, timers = fetches
    FakeFetch.hang = True
    win._refresh_server()
    first = win._fetch
    timers.pop()[1]()  # 30 s later, still waiting on the stats site
    assert win._fetch is first and len(timers) == 1  # no second fetch, but still ticking
    first.running = False
    timers.pop()[1]()
    assert win._fetch is not first


def test_save_writes_settings_and_schedules(win, calls):
    win.hour.set("19")
    win.minute.set("05")
    win.launcher.set("steam")
    win.save()
    saved = Config.load()
    assert (saved.start_time, saved.launcher) == ("19:05", "steam")
    assert calls == [("schedule", "19:05")]
    assert win.status.cget("text").startswith("Saved. Seeds every day at 19:05.")


def test_save_without_automatic_seeding_unschedules(win, calls):
    win.enabled.set(False)
    win.save()
    assert calls == [("unschedule",)]


def test_scheduling_error_is_shown(win, monkeypatch):
    def fail(start):
        raise RuntimeError("Access is denied.")

    monkeypatch.setattr(schedule, "schedule", fail)
    win.save()
    assert win.status.cget("text") == "Couldn't set up the schedule: Access is denied."
    assert str(win.status.cget("foreground")) == window.FLARE


def test_seed_now_saves_then_starts(win, calls):
    win.seed_now()
    assert calls == [("schedule", "06:35"), ("seed",)]
    assert win.status.cget("text").startswith("Seeding started.")


@pytest.mark.parametrize("count", [79, None])  # below 80, or the stats site unreachable
def test_seed_now_starts_unless_the_count_says_seeded(win, calls, count):
    win._show_server(count)
    win.seed_now()
    assert calls[-1] == ("seed",)


def test_seed_now_when_the_server_is_already_seeded(win, calls):
    win._show_server(84)
    win.seed_now()
    assert calls == [("schedule", "06:35")]  # settings saved, no run
    assert win.status.cget("text") == "The server is already seeded (84 players), so there's nothing to do."


def test_seed_now_when_the_game_is_open(win, calls, monkeypatch):
    monkeypatch.setattr(window.Game, "running", lambda self: True)
    win.seed_now()
    assert calls == [("schedule", "06:35")]
    assert win.status.cget("text").startswith("The game is already open.")


def test_seed_now_when_already_seeding(win, calls, monkeypatch):
    monkeypatch.setattr(window.instance, "seeding_processes", lambda: [object()])
    win.seed_now()
    assert calls == []
    assert win.status.cget("text") == "Already seeding."


def test_stop_with_nothing_running(win, monkeypatch):
    monkeypatch.setattr(window.instance, "stop_seeding", lambda: False)
    win.stop()
    assert win.status.cget("text") == "Nothing is seeding right now."


@needs_display
def test_opens_in_a_fresh_process(tmp_path):
    """The way the exe starts, DPI awareness included, which can only be set once per process."""
    script = """if True:
        from seeder import schedule, window
        from seeder.config import Config
        schedule.is_scheduled = lambda: False
        window.SetupWindow._load_server = lambda self: None
        w = window.SetupWindow(Config())
        w.root.update()
        assert w.root.winfo_width() == w._image("header").width(), w.root.winfo_width()
        w.root.destroy()
    """
    env = {**os.environ, "APPDATA": str(tmp_path)}
    done = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=env, capture_output=True, text=True,
                          timeout=120)
    assert done.returncode == 0, done.stderr
