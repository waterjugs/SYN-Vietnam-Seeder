"""Thin ctypes wrappers for the Windows calls the seeder needs.

Kept in one place so the rest of the code stays testable on any OS. Keys go
out through SendInput with scancodes looked up for the game's keyboard
layout, so QWERTZ/AZERTY players get the right letters, and text is typed
as Unicode characters.
"""

from __future__ import annotations

import ctypes
import logging
import threading
import time
from ctypes import wintypes

log = logging.getLogger(__name__)

user32 = ctypes.WinDLL("user32", use_last_error=True)  # type: ignore[attr-defined]
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]

INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
KEYEVENTF_KEYUP, KEYEVENTF_UNICODE, KEYEVENTF_SCANCODE = 0x2, 0x4, 0x8
MOUSEEVENTF_MOVE, MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x1, 0x2, 0x4
GW_OWNER = 4
VK = {"space": 0x20, "enter": 0x0D, "esc": 0x1B, "backspace": 0x08, "alt": 0x12}
MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x1, 0x2, 0x4000
FLASHW_TRAY, FLASHW_TIMERNOFG = 0x2, 0xC
VK_END = 0x23
WM_HOTKEY = 0x0312


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


class FLASHWINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("hwnd", wintypes.HWND), ("dwFlags", wintypes.DWORD),
                ("uCount", wintypes.UINT), ("dwTimeout", wintypes.DWORD)]


def _prototypes() -> None:
    """64-bit safe signatures; ctypes would otherwise truncate handles to int."""
    H, U, D = wintypes.HWND, wintypes.UINT, wintypes.DWORD
    specs = {
        "GetForegroundWindow": ([], H),
        "GetWindow": ([H, U], H),
        "GetWindowThreadProcessId": ([H, ctypes.POINTER(D)], D),
        "IsWindowVisible": ([H], wintypes.BOOL),
        "IsIconic": ([H], wintypes.BOOL),
        "SetForegroundWindow": ([H], wintypes.BOOL),
        "ShowWindowAsync": ([H, ctypes.c_int], wintypes.BOOL),
        "IsHungAppWindow": ([H], wintypes.BOOL),
        "GetLastInputInfo": ([ctypes.POINTER(LASTINPUTINFO)], wintypes.BOOL),
        "FlashWindowEx": ([ctypes.POINTER(FLASHWINFO)], wintypes.BOOL),
        "GetWindowRect": ([H, ctypes.POINTER(wintypes.RECT)], wintypes.BOOL),
        "GetClientRect": ([H, ctypes.POINTER(wintypes.RECT)], wintypes.BOOL),
        "ClientToScreen": ([H, ctypes.POINTER(wintypes.POINT)], wintypes.BOOL),
        "OpenInputDesktop": ([D, wintypes.BOOL, D], wintypes.HANDLE),
        "CloseDesktop": ([wintypes.HANDLE], wintypes.BOOL),
        "SetCursorPos": ([ctypes.c_int, ctypes.c_int], wintypes.BOOL),
        "GetKeyboardLayout": ([D], wintypes.HKL),
        "VkKeyScanExW": ([wintypes.WCHAR, wintypes.HKL], wintypes.SHORT),
        "MapVirtualKeyExW": ([U, U, wintypes.HKL], U),
        "SendInput": ([U, ctypes.POINTER(INPUT), ctypes.c_int], U),
        "RegisterHotKey": ([H, ctypes.c_int, U, U], wintypes.BOOL),
        "GetMessageW": ([ctypes.POINTER(wintypes.MSG), H, U, U], wintypes.BOOL),
    }
    for name, (args, res) in specs.items():
        fn = getattr(user32, name)
        fn.argtypes, fn.restype = args, res
    for name, (args, res) in {"GetTickCount": ([], D)}.items():
        fn = getattr(kernel32, name)
        fn.argtypes, fn.restype = args, res


_prototypes()

SW_RESTORE = 9
# Windows counts the seeder's own input as activity too. So before sending
# any, note whether the latest input was the player's; user_idle_seconds()
# then uses that instead of ours. Ticks are GetTickCount() values.
_own_input_tick: int | None = None
_player_input_tick: int | None = None
OWN_INPUT_SLACK_MS = 250  # how long after we send input Windows may stamp it
# The window our input is for (the game, set by Game.focus()). Input is
# dropped if another window has come to the front since, e.g. the player
# clicked back into their browser halfway through typing the server name.
_input_target: int | None = None


def _ours(last_input: int, own_input: int | None) -> bool:
    return own_input is not None and (last_input - own_input) & 0xFFFFFFFF <= OWN_INPUT_SLACK_MS


def _mark_own_input() -> None:
    global _own_input_tick, _player_input_tick
    info = LASTINPUTINFO(cbSize=ctypes.sizeof(LASTINPUTINFO))
    if user32.GetLastInputInfo(ctypes.byref(info)) and not _ours(info.dwTime, _own_input_tick):
        _player_input_tick = info.dwTime
    _own_input_tick = kernel32.GetTickCount()


def set_input_target(hwnd: int | None) -> None:
    global _input_target
    _input_target = hwnd


def _on_target() -> bool:
    return not _input_target or user32.GetForegroundWindow() == _input_target


def _send(*inputs: INPUT, always: bool = False) -> None:
    """``always`` sends even when the game isn't in front: for releasing keys
    and buttons (harmless in any window, and they mustn't stay held down) and
    for force_to_front()'s nudges."""
    if not always and not _on_target():
        return
    _mark_own_input()
    array = (INPUT * len(inputs))(*inputs)
    user32.SendInput(len(inputs), array, ctypes.sizeof(INPUT))


def _key(scan: int = 0, vk: int = 0, flags: int = 0) -> INPUT:
    return INPUT(type=INPUT_KEYBOARD, u=_INPUTUNION(ki=KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags)))


def make_dpi_aware() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        pass


# Windows

def window_pid(hwnd: int) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def main_window(pid: int) -> int | None:
    """The process's largest visible, unowned top-level window."""
    best: list[tuple[int, int]] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _):
        if window_pid(hwnd) == pid and user32.IsWindowVisible(hwnd) and not user32.GetWindow(hwnd, GW_OWNER):
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            best.append(((rect.right - rect.left) * (rect.bottom - rect.top), hwnd))
        return True

    user32.EnumWindows(callback, 0)
    return max(best)[1] if best else None


def client_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    """(left, top, width, height) of the window's client area on the virtual desktop."""
    rect = wintypes.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        return None
    origin = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(origin))
    if rect.right <= 0 or rect.bottom <= 0:
        return None
    return origin.x, origin.y, rect.right, rect.bottom


def in_front(hwnd: int) -> bool:
    return user32.GetForegroundWindow() == hwnd


def foreground_pid() -> int:
    hwnd = user32.GetForegroundWindow()
    return window_pid(hwnd) if hwnd else 0


def bring_to_front(hwnd: int) -> bool:
    """Asks Windows to make hwnd the foreground window. Returns True once it
    is, and isn't minimised.

    Windows refuses while someone is using another window, which is what we
    want then (a minimised game stays minimised too); force_to_front() is
    for when the PC has been left alone.
    """
    if user32.GetForegroundWindow() != hwnd:
        user32.SetForegroundWindow(hwnd)
        if user32.GetForegroundWindow() != hwnd:
            return False
    if user32.IsIconic(hwnd):
        user32.ShowWindowAsync(hwnd, SW_RESTORE)  # async: a frozen game can't block us
        return False  # ready on the next try
    return True


def force_to_front(hwnd: int, alt_tap: bool = True) -> bool:
    """Makes hwnd the foreground window even though another program has it.
    Only for when nobody is using the PC. Returns True if it worked.

    Windows lets the program that sent the latest input change the
    foreground window, so this first sends a mouse move of zero pixels:
    input that no window reacts to. That also works when the foreground is
    an invisible window, like the "Windows Input Experience" that took over
    in a live test (2026-10-26). An Alt tap is the fallback.
    """
    if user32.IsHungAppWindow(hwnd):
        return False  # not answering messages; activating it could block us
    if user32.IsIconic(hwnd):
        user32.ShowWindowAsync(hwnd, SW_RESTORE)
    if bring_to_front(hwnd):
        return True
    _send(INPUT(type=INPUT_MOUSE, u=_INPUTUNION(mi=MOUSEINPUT(dwFlags=MOUSEEVENTF_MOVE))), always=True)
    if _ask_for_front(hwnd):
        return True
    if alt_tap and user32.GetForegroundWindow() != hwnd:  # if it's ours, it's only still restoring
        # Nobody is typing, so the Alt can't land in their work.
        _send(_key(vk=VK["alt"]), _key(vk=VK["alt"], flags=KEYEVENTF_KEYUP), always=True)
        return _ask_for_front(hwnd)
    return False


def _ask_for_front(hwnd: int, tries: int = 5) -> bool:
    """SetForegroundWindow, retried briefly: SendInput only queues the input,
    and the right to change the foreground comes once Windows handles it."""
    for _ in range(tries):
        time.sleep(0.05)
        if user32.GetForegroundWindow() != hwnd:
            user32.SetForegroundWindow(hwnd)
        if user32.GetForegroundWindow() == hwnd and not user32.IsIconic(hwnd):  # restored, not just in front
            return True
    return False


def user_idle_seconds() -> float:
    """Seconds since the player last used the mouse or keyboard; the
    seeder's own input doesn't count."""
    info = LASTINPUTINFO(cbSize=ctypes.sizeof(LASTINPUTINFO))
    if not user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    return idle_ms(kernel32.GetTickCount(), info.dwTime, _own_input_tick, _player_input_tick) / 1000


def idle_ms(now: int, last_input: int, own_input: int | None, player_input: int | None) -> int:
    """Milliseconds of player inactivity from GetTickCount() values, which
    wrap around every 49.7 days."""
    if _ours(last_input, own_input):
        # The latest input was ours; the player's came before it.
        last_input = player_input if player_input is not None else own_input
    return (now - last_input) & 0xFFFFFFFF


def flash(hwnd: int) -> None:
    """Flashes the window's taskbar button until it comes to the front."""
    info = FLASHWINFO(cbSize=ctypes.sizeof(FLASHWINFO), hwnd=hwnd,
                      dwFlags=FLASHW_TRAY | FLASHW_TIMERNOFG, uCount=0, dwTimeout=0)
    user32.FlashWindowEx(ctypes.byref(info))


def desktop_unlocked() -> bool:
    """False while the PC is locked (input can't reach a locked desktop)."""
    desktop = user32.OpenInputDesktop(0, False, 0x0100)  # DESKTOP_SWITCHDESKTOP
    if not desktop:
        return False
    user32.CloseDesktop(desktop)
    return True


# Input

def click_at(x: int, y: int) -> None:
    if not _on_target():
        return  # leave the player's cursor alone
    user32.SetCursorPos(x, y)
    time.sleep(0.1)
    down = INPUT(type=INPUT_MOUSE, u=_INPUTUNION(mi=MOUSEINPUT(dwFlags=MOUSEEVENTF_LEFTDOWN)))
    up = INPUT(type=INPUT_MOUSE, u=_INPUTUNION(mi=MOUSEINPUT(dwFlags=MOUSEEVENTF_LEFTUP)))
    _send(down)
    time.sleep(0.05)
    _send(up, always=True)


def move_cursor(x: int, y: int) -> None:
    if _on_target():
        user32.SetCursorPos(x, y)


def _scancode(key: str) -> int:
    """Scancode of the key that produces ``key`` on the foreground window's layout."""
    if key in VK:
        vk = VK[key]
        layout = None
    else:
        thread = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
        layout = user32.GetKeyboardLayout(thread)
        vk = user32.VkKeyScanExW(key, layout) & 0xFF
    return user32.MapVirtualKeyExW(vk, 0, layout)  # MAPVK_VK_TO_VSC


def key_down(key: str) -> None:
    _send(_key(scan=_scancode(key), flags=KEYEVENTF_SCANCODE))


def key_up(key: str) -> None:
    _send(_key(scan=_scancode(key), flags=KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP), always=True)


def press(key: str) -> None:
    key_down(key)
    time.sleep(0.05)
    key_up(key)


def type_text(text: str) -> None:
    for ch in text:
        _send(_key(scan=ord(ch), flags=KEYEVENTF_UNICODE),
              _key(scan=ord(ch), flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))
        time.sleep(0.04)


# Stop hotkey

def listen_for_stop_hotkey(stop: threading.Event) -> None:
    """Sets ``stop`` when Ctrl+Alt+End is pressed anywhere. Runs a daemon thread."""

    def loop() -> None:
        if not user32.RegisterHotKey(None, 1, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, VK_END):
            log.warning("Couldn't register the Ctrl+Alt+End stop key")
            return
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY:
                log.info("Ctrl+Alt+End pressed; stopping")
                stop.set()
                return

    threading.Thread(target=loop, daemon=True, name="stop-hotkey").start()
