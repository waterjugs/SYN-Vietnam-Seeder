"""Game.focus() and the Windows calls behind it, with the DLLs faked."""

import ctypes
import importlib.util
import logging
import os
import sys
import types

import psutil
import pytest

import seeder
from seeder.config import Config
from seeder.game import IDLE_BEFORE_TAKEOVER, Game


class FakeWinapi(types.ModuleType):
    def __init__(self):
        super().__init__("seeder.winapi")
        self.polite = False  # bring_to_front() works
        self.forced = True  # force_to_front() works
        self.idle = 0.0
        self.calls: list[str] = []
        self.target = None
        self.front_pid = 0
        self.restoring = False  # the game is in front but still minimised

    def foreground_pid(self):
        return self.front_pid

    def in_front(self, hwnd):
        return self.restoring

    def set_input_target(self, hwnd):
        self.target = hwnd

    def bring_to_front(self, hwnd):
        self.calls.append("ask")
        return self.polite

    def force_to_front(self, hwnd, alt_tap=True):
        self.calls.append("force+alt" if alt_tap else "force")
        return self.forced

    def user_idle_seconds(self):
        return self.idle

    def flash(self, hwnd):
        self.calls.append("flash")


@pytest.fixture
def fake(monkeypatch):
    api = FakeWinapi()
    monkeypatch.setitem(sys.modules, "seeder.winapi", api)
    monkeypatch.setattr(seeder, "winapi", api, raising=False)
    return api


@pytest.fixture
def game(monkeypatch):
    g = Game(Config())
    monkeypatch.setattr(g, "window", lambda: 1234)
    return g


def test_in_front_when_windows_allows_it(fake, game):
    fake.polite = True
    assert game.focus()
    assert fake.calls == ["ask"]
    assert fake.target == 1234


def test_waits_while_someone_uses_the_pc(fake, game, caplog):
    fake.idle = IDLE_BEFORE_TAKEOVER - 1
    with caplog.at_level(logging.WARNING):
        assert not game.focus()
        assert not game.focus()
    assert not any(c.startswith("force") for c in fake.calls)  # never yanks the screen from someone using it
    assert fake.calls.count("flash") == 1
    assert sum("in use" in r.message for r in caplog.records) == 1
    assert game.waiting_for_user()
    assert fake.target == 1234  # so input meant for the game is dropped meanwhile


def test_takes_the_front_once_the_pc_is_idle(fake, game, caplog):
    fake.idle = 1
    assert not game.focus()
    fake.idle = IDLE_BEFORE_TAKEOVER
    with caplog.at_level(logging.INFO):
        assert game.focus()
    assert fake.calls[-1] == "force+alt"
    assert "Brought the game to the front" in caplog.text
    assert not game.waiting_for_user()
    # Someone grabs another window again: a new wait, flagged again.
    fake.idle = 0
    assert not game.focus()
    assert fake.calls.count("flash") == 2


def test_refused_takeover_taps_alt_only_once_and_logs_once(fake, game, caplog):
    fake.idle, fake.forced = 60, False
    fake.front_pid = os.getpid()
    with caplog.at_level(logging.WARNING):
        for _ in range(4):
            assert not game.focus()
    assert [c for c in fake.calls if c.startswith("force")] == ["force+alt", "force", "force", "force"]
    refused = [r.message for r in caplog.records if "Couldn't bring the game to the front" in r.message]
    assert len(refused) == 1
    assert f"({psutil.Process().name()} has it)" in refused[0]  # says which program is in the way
    assert "flash" not in fake.calls
    assert not game.waiting_for_user()  # refused isn't the player's doing; timeouts still apply
    # Once it gets to the front, the next wait may tap Alt again.
    fake.forced = True
    assert game.focus()
    fake.forced = False
    game.focus()
    assert fake.calls[-1] == "force+alt"


def test_a_game_still_restoring_is_not_a_refusal(fake, game, caplog):
    fake.idle, fake.forced, fake.restoring = 60, False, True
    with caplog.at_level(logging.WARNING):
        assert not game.focus()
    assert not caplog.records  # nothing is in the way; it's ready on the next try
    fake.restoring = False
    game.focus()
    assert fake.calls[-1] == "force+alt"  # the Alt tap wasn't used up


def test_no_window_no_focus(fake, monkeypatch):
    g = Game(Config())
    monkeypatch.setattr(g, "window", lambda: None)
    assert not g.focus()
    assert fake.calls == []


# The real seeder.winapi, on stub DLLs that record calls.

class Fn:
    def __init__(self, calls, name):
        self.calls, self.name = calls, name
        self.argtypes = self.restype = None
        self.ret = 0

    def __call__(self, *args):
        self.calls.append(self.name)
        return self.ret(*args) if callable(self.ret) else self.ret


class Dll:
    def __init__(self, calls):
        self._calls = calls

    def __getattr__(self, name):
        fn = Fn(self._calls, name)
        setattr(self, name, fn)
        return fn


@pytest.fixture
def winapi(monkeypatch):
    """A private copy of seeder.winapi: sys.modules and the package are left alone."""
    calls: list[str] = []
    dlls: dict[str, Dll] = {}
    monkeypatch.setattr(ctypes, "WinDLL", lambda name, **_: dlls.setdefault(name, Dll(calls)), raising=False)
    spec = importlib.util.find_spec("seeder.winapi")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.calls = calls
    module.user32.GetForegroundWindow.ret = 999  # the player's browser
    module.user32.IsIconic.ret = 0
    module.user32.IsHungAppWindow.ret = 0
    calls.clear()
    return module


def test_bring_to_front_sends_nothing_and_leaves_a_minimised_game_when_refused(winapi):
    winapi.user32.IsIconic.ret = 1
    assert not winapi.bring_to_front(1234)
    assert "SendInput" not in winapi.calls
    assert "ShowWindowAsync" not in winapi.calls


def test_bring_to_front_restores_a_minimised_game_once_it_is_ours(winapi):
    winapi.user32.GetForegroundWindow.ret = 1234
    winapi.user32.IsIconic.ret = 1
    assert not winapi.bring_to_front(1234)  # ready on the next try
    assert "ShowWindowAsync" in winapi.calls
    winapi.user32.IsIconic.ret = 0
    assert winapi.bring_to_front(1234)


def sent_inputs(winapi):
    """Records SendInput calls as lists of INPUT copies."""
    sent = []
    winapi.user32.SendInput.ret = lambda n, array, size: sent.append([array[i] for i in range(n)]) or n
    return sent


def front_after(winapi, kind, sent, monkeypatch):
    """Windows grants the front once input of ``kind`` (mouse or keyboard) went out."""
    monkeypatch.setattr(winapi.time, "sleep", lambda s: None)
    state = {"front": 999}

    def set_front(hwnd):
        if any(batch[0].type == kind for batch in sent):
            state["front"] = hwnd
        return state["front"] == hwnd

    winapi.user32.SetForegroundWindow.ret = set_front
    winapi.user32.GetForegroundWindow.ret = lambda: state["front"]


def test_force_to_front_sends_a_zero_mouse_move_then_asks(winapi, monkeypatch):
    sent = sent_inputs(winapi)
    front_after(winapi, winapi.INPUT_MOUSE, sent, monkeypatch)
    winapi.set_input_target(1234)  # the game, not in front: the move goes out anyway
    assert winapi.force_to_front(1234)
    assert len(sent) == 1 and len(sent[0]) == 1
    move = sent[0][0]
    assert move.type == winapi.INPUT_MOUSE and move.u.mi.dwFlags == winapi.MOUSEEVENTF_MOVE
    assert (move.u.mi.dx, move.u.mi.dy) == (0, 0)  # the cursor doesn't move
    assert "AttachThreadInput" not in winapi.calls


def test_force_to_front_falls_back_to_an_alt_tap(winapi, monkeypatch):
    sent = sent_inputs(winapi)
    front_after(winapi, winapi.INPUT_KEYBOARD, sent, monkeypatch)
    assert winapi.force_to_front(1234, alt_tap=True)
    assert [batch[0].type for batch in sent] == [winapi.INPUT_MOUSE, winapi.INPUT_KEYBOARD]
    alt = sent[1]
    assert [i.u.ki.wVk for i in alt] == [winapi.VK["alt"]] * 2
    assert alt[1].u.ki.dwFlags & winapi.KEYEVENTF_KEYUP  # released again


def test_force_to_front_without_alt_tap_sends_only_the_mouse_move(winapi, monkeypatch):
    sent = sent_inputs(winapi)
    front_after(winapi, winapi.INPUT_KEYBOARD, sent, monkeypatch)
    assert not winapi.force_to_front(1234, alt_tap=False)
    assert [batch[0].type for batch in sent] == [winapi.INPUT_MOUSE]


def test_force_to_front_waits_for_windows_to_handle_the_move(winapi, monkeypatch):
    events = []
    monkeypatch.setattr(winapi.time, "sleep", lambda s: events.append("sleep"))
    winapi.user32.SendInput.ret = lambda n, array, size: events.append("input") or n
    state = {"front": 999}

    def set_front(hwnd):
        events.append("ask")
        # Windows handles queued input a moment later: the second ask after it works.
        if "input" in events and events[events.index("input"):].count("ask") >= 2:
            state["front"] = hwnd
        return state["front"] == hwnd

    winapi.user32.SetForegroundWindow.ret = set_front
    winapi.user32.GetForegroundWindow.ret = lambda: state["front"]
    assert winapi.force_to_front(1234)
    after = events[events.index("input") + 1:]
    assert after[:4] == ["sleep", "ask", "sleep", "ask"]  # waits before each ask
    assert events.count("input") == 1  # no Alt needed


def test_force_to_front_no_alt_when_the_game_is_in_front_but_still_minimised(winapi, monkeypatch):
    sent = sent_inputs(winapi)
    front_after(winapi, winapi.INPUT_MOUSE, sent, monkeypatch)
    winapi.user32.IsIconic.ret = 1  # the restore hasn't been handled yet
    assert not winapi.force_to_front(1234, alt_tap=True)
    assert [batch[0].type for batch in sent] == [winapi.INPUT_MOUSE]
    assert winapi.in_front(1234)
    winapi.user32.IsIconic.ret = 0
    assert winapi.bring_to_front(1234)  # ready on the next try


def test_force_to_front_leaves_a_hung_game_alone(winapi):
    winapi.user32.IsHungAppWindow.ret = 1
    assert not winapi.force_to_front(1234)
    assert "SendInput" not in winapi.calls
    assert "SetForegroundWindow" not in winapi.calls


def test_input_is_dropped_when_the_game_lost_the_front(winapi, monkeypatch):
    monkeypatch.setattr(winapi.time, "sleep", lambda s: None)
    winapi.user32.MapVirtualKeyExW.ret = 0x21
    winapi.set_input_target(1234)  # the browser (999) is in front
    winapi.click_at(10, 10)
    winapi.move_cursor(10, 10)
    winapi.type_text("syndicate")
    winapi.key_down("f")
    assert "SendInput" not in winapi.calls and "SetCursorPos" not in winapi.calls
    winapi.key_up("f")  # releases always go, so nothing stays held down
    assert winapi.calls.count("SendInput") == 1
    winapi.user32.GetForegroundWindow.ret = 1234
    winapi.press("f")
    assert winapi.calls.count("SendInput") == 3


def test_seeders_own_input_does_not_reset_the_idle_time(winapi):
    last = {"tick": 10_000}  # the player last touched the PC at 10 s
    winapi.user32.GetLastInputInfo.ret = lambda info: setattr(info._obj, "dwTime", last["tick"]) or 1
    winapi.kernel32.GetTickCount.ret = 20_000
    winapi.user32.GetForegroundWindow.ret = 1234
    winapi.set_input_target(1234)
    winapi.press("f")  # the seeder presses F at 20 s
    last["tick"] = 20_016  # Windows stamps our key-up
    winapi.press("f")  # ...and again: our earlier press must not be taken for the player
    last["tick"] = 20_030
    winapi.kernel32.GetTickCount.ret = 40_000
    assert winapi.user_idle_seconds() == 30.0  # since the player's 10 s, not our 20 s
    last["tick"] = 39_000  # the player moves the mouse
    assert winapi.user_idle_seconds() == 1.0


def test_idle_counts_from_the_last_input(winapi):
    assert winapi.idle_ms(now=50_000, last_input=20_000, own_input=None, player_input=None) == 30_000
    # The latest input was ours: count from the player's, or from ours if we never saw theirs.
    assert winapi.idle_ms(now=50_000, last_input=20_016, own_input=20_000, player_input=5_000) == 45_000
    assert winapi.idle_ms(now=50_000, last_input=20_016, own_input=20_000, player_input=None) == 30_000
    # The player moved the mouse after our click.
    assert winapi.idle_ms(now=50_000, last_input=45_000, own_input=20_000, player_input=5_000) == 5_000


def test_idle_survives_tick_wraparound(winapi):
    assert winapi.idle_ms(now=1_000, last_input=2**32 - 4_000, own_input=None, player_input=None) == 5_000
    assert winapi.idle_ms(now=1_000, last_input=2**32 - 4_000, own_input=2**32 - 4_100,
                          player_input=2**32 - 9_000) == 10_000
