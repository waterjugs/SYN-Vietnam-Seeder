import tkinter as tk

import pytest

from seeder import crcon, schedule, window
from seeder.config import Config

LOAD_SERVER = window.SetupWindow._load_server  # the fixture swaps it out


@pytest.fixture
def calls(monkeypatch, tmp_path):
    """Records what the window asks of the scheduler and the seeder; nothing real happens."""
    try:
        tk.Tk().destroy()
    except tk.TclError:
        pytest.skip("no display for Tk")
    monkeypatch.setenv("APPDATA", str(tmp_path))  # config.json lands here
    made = []
    monkeypatch.setattr(schedule, "is_scheduled", lambda: True)
    monkeypatch.setattr(schedule, "schedule", lambda start: made.append(("schedule", start)))
    monkeypatch.setattr(schedule, "unschedule", lambda: made.append(("unschedule",)))
    monkeypatch.setattr(window, "_start_seed_process", lambda: made.append(("seed",)))
    monkeypatch.setattr(window.instance, "seeding_processes", lambda: [])
    monkeypatch.setattr(window.SetupWindow, "_load_server", lambda self: None)  # no thread, no network
    return made


@pytest.fixture
def win(calls):
    w = window.SetupWindow(Config(start_time="06:35", launcher="epic"))
    yield w
    w.root.destroy()


@pytest.mark.parametrize("dpi", [96, 144, 192])  # 100%, 150% (resized from 2x) and 200%
def test_opens_at_any_scaling(calls, monkeypatch, dpi):
    monkeypatch.setattr(tk.Misc, "winfo_fpixels", lambda self, distance: float(dpi))
    w = window.SetupWindow(Config())
    w.root.update()
    assert w.scale == dpi / 96
    assert w.root.winfo_width() == w._image("header").width() == round(480 * dpi / 96)
    w.root.destroy()


def test_shows_settings(win):
    assert (win.hour.get(), win.minute.get(), win.launcher.get()) == ("06", "35", "epic")
    assert win.enabled.get()
    assert win.status.cget("text").startswith("Seeds every day at 06:35.")


def test_server_count(win):
    win._show_server(37)
    assert (win.count.cget("text"), win.need.cget("text")) == ("37", "Needs 43 more")
    win._show_server(84)
    assert win.need.cget("text") == "Seeded"
    win._show_server(None)
    assert str(win.server.cget("text")) == "Couldn't reach the server stats."
    assert not win.count.winfo_ismapped()


def test_load_server_shows_the_count(win, monkeypatch):
    monkeypatch.setattr(crcon, "fetch", lambda url: crcon.ServerStatus("x", 12, 6, 6, 0))
    LOAD_SERVER(win)
    win.root.update()
    assert (win.count.cget("text"), win.need.cget("text")) == ("12", "Needs 68 more")


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


def test_seed_now_when_already_seeding(win, calls, monkeypatch):
    monkeypatch.setattr(window.instance, "seeding_processes", lambda: [object()])
    win.seed_now()
    assert calls == []
    assert win.status.cget("text") == "Already seeding."


def test_stop_with_nothing_running(win, monkeypatch):
    monkeypatch.setattr(window.instance, "stop_seeding", lambda: False)
    win.stop()
    assert win.status.cget("text") == "Nothing is seeding right now."
