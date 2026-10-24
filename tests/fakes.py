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
    """``visible`` is the set of templates on screen; clicking one applies
    ``transitions[name] = (hide, show)``."""

    def __init__(self, transitions: dict[str, tuple[set[str], set[str]]]):
        self.visible: set[str] = set()
        self.transitions = transitions
        self.clicks: list[str] = []
        self.typed: list[str] = []
        self.keys: list[str] = []

    def find_any(self, names):
        for name in names:
            if name in self.visible:
                return name, (hash(name), 0)
        return None

    def click(self, pos):
        name = next(n for n in self.visible if hash(n) == pos[0])
        self.clicks.append(name)
        hide, show = self.transitions.get(name, ({name}, set()))
        self.visible = (self.visible - hide) | show

    def type_text(self, text):
        self.typed.append(text)

    def press(self, key):
        self.keys.append(key)

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

    def launch(self) -> bool:
        self.launches += 1
        if self.launch_ok:
            self.is_running = True
            self.screen.visible = {"menu_play"}
        return self.launch_ok

    def focus(self) -> None:
        pass

    def close(self) -> None:
        self.closes += 1
        self.is_running = False
        self.screen.visible = set()


# The menu flow as currently expected for HLL Vietnam.
HAPPY_PATH = {
    "menu_play": ({"menu_play"}, {"browser_search"}),
    "browser_search": ({"browser_search"}, {"server_row"}),
    "server_row": ({"server_row"}, {"browser_join"}),
    "browser_join": ({"browser_join"}, {"team_us", "team_nva"}),
    "team_us": ({"team_us", "team_nva"}, {"role_rifleman"}),
    "team_nva": ({"team_us", "team_nva"}, {"role_rifleman"}),
    "role_rifleman": ({"role_rifleman"}, {"spawn_hq", "deploy_button"}),
    "spawn_hq": ({"spawn_hq"}, set()),
    "deploy_button": ({"deploy_button"}, set()),
}
