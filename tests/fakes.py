"""Stand-ins for the screen, game and clock so the flow runs without Windows."""

from __future__ import annotations


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class FakeScreen:
    """``visible`` is the set of templates on screen.

    ``transitions`` maps an action to (hide, show): a template name for a
    click on it, or ``(template, key)`` for a key pressed while that
    template is visible.
    """

    def __init__(self, transitions):
        self.visible: set[str] = set()
        self.transitions = transitions
        self.clicks: list[str] = []
        self.typed: list[str] = []
        self.keys: list[str] = []
        self.refreshes = 0

    def _apply(self, action):
        hide, show = self.transitions[action]
        self.visible = (self.visible - hide) | show

    def refresh(self):
        self.refreshes += 1

    def find(self, name, region=None):
        return (hash(name), 0) if name in self.visible else None

    def find_all(self, name, region=None):
        pos = self.find(name)
        return [pos] if pos else []

    def click(self, pos):
        name = next(n for n in self.visible if hash(n) == pos[0])
        self.clicks.append(name)
        if name in self.transitions:
            self._apply(name)

    def type_text(self, text):
        self.typed.append(text)

    def press(self, key):
        self.keys.append(key)
        for name in sorted(self.visible):
            if (name, key) in self.transitions:
                self._apply((name, key))
                return

    def hold(self, key, seconds):
        self.keys.append(key)


class FakeGame:
    def __init__(self, screen: FakeScreen, running: bool = False, launch_ok: bool = True):
        self.screen = screen
        self.is_running = running
        self.launch_ok = launch_ok
        self.launches = 0
        self.closes = 0

    def running(self) -> bool:
        return self.is_running

    def launch(self, timeout=None) -> bool:
        self.launches += 1
        if self.launch_ok:
            self.is_running = True
            self.screen.visible = {"splash"}
        return self.launch_ok

    focused = True
    locked = False

    def focus(self) -> bool:
        return self.is_running and self.focused

    def unlocked(self) -> bool:
        return not self.locked

    def close(self, linger: float = 0) -> None:
        self.closes += 1
        self.lingered = linger
        self.is_running = False
        self.screen.visible = set()


# HLL Vietnam's join flow as seen on 2026-10-24 (v1.7). "splash" isn't a
# template the seeder looks for; it stands in for the press-any-button screen.
HAPPY_PATH = {
    ("splash", "space"): ({"splash"}, {"menu_enlist"}),
    "menu_enlist": ({"menu_enlist"}, {"browser_search", "browser_refresh", "browser_join"}),
    ("browser_search", "enter"): ({"browser_search"}, {"server_row"}),
    ("browser_refresh", "r"): (set(), set()),
    "browser_join": ({"server_row", "browser_join", "browser_refresh"}, {"switch_team", "faction_nva", "squad_join", "infantry_create"}),
    "squad_join": ({"switch_team", "faction_nva", "squad_join", "infantry_create"}, {"roles_confirm", "admin_yes"}),
    "infantry_create": ({"switch_team", "faction_nva", "squad_join", "infantry_create"}, {"roles_confirm"}),
    "switch_team": ({"faction_nva"}, set()),
    "admin_yes": ({"admin_yes"}, set()),
    ("roles_confirm", "f"): ({"roles_confirm"}, {"deploy_button"}),
    ("deploy_button", "f"): ({"deploy_button"}, set()),
    ("game_menu_leave", "esc"): ({"game_menu_leave"}, set()),
}
