from seeder import flow, runner
from seeder.config import Config
from seeder.crcon import ServerStatus

from .fakes import HAPPY_PATH, FakeClock, FakeGame, FakeScreen

UNITS = {"switch_team", "faction_nva", "squad_join", "infantry_create"}


def statuses(*counts, allied_heavy=True):
    """A fetch() that returns each count in turn, then repeats the last."""
    queue = list(counts)

    def fetch(_url):
        count = queue.pop(0) if len(queue) > 1 else queue[0]
        if count is None:
            return None
        big, small = count - count // 2, count // 2
        allied, axis = (big, small) if allied_heavy else (small, big)
        return ServerStatus("Syndicate", count, allied, axis, 3000)

    return fetch


def make(running=False, launch_ok=True):
    screen = FakeScreen(HAPPY_PATH)
    game = FakeGame(screen, running=running, launch_ok=launch_ok)
    return Config(), game, screen, FakeClock()


def test_skips_when_already_seeded():
    config, game, screen, clock = make()
    assert runner.seed(config, game, screen, statuses(85), clock) is runner.Outcome.ALREADY_SEEDED
    assert game.launches == 0


def test_skips_when_server_down():
    config, game, screen, clock = make()
    assert runner.seed(config, game, screen, statuses(None), clock) is runner.Outcome.SERVER_DOWN
    assert game.launches == 0


def test_leaves_a_running_game_alone():
    config, game, screen, clock = make(running=True)
    assert runner.seed(config, game, screen, statuses(10), clock) is runner.Outcome.GAME_IN_USE
    assert game.closes == 0 and screen.clicks == [] and screen.keys == []


def test_full_join_then_leaves_once_seeded():
    config, game, screen, clock = make()
    fetch = statuses(10, 10, 40, 79, 80)
    assert runner.seed(config, game, screen, fetch, clock) is runner.Outcome.SEEDED
    assert screen.typed == ["syndicate"]
    assert screen.clicks == ["menu_enlist", "browser_search", "browser_join", "admin_yes", "force_us", "squad_join"]
    assert screen.keys[:2] == ["space", "enter"]
    assert [k for k in screen.keys if k == "f"] == ["f", "f"]
    assert game.launches == 1 and not game.is_running


def test_keeps_game_team_when_balanced():
    config, game, screen, clock = make()
    runner.seed(config, game, screen, statuses(11, 80), clock)  # 6 v 5
    assert "switch_team" not in screen.clicks


def test_select_force_picks_the_smaller_team():
    config, game, screen, clock = make()
    runner.seed(config, game, screen, statuses(11, 80), clock)  # allies 6, axis 5
    assert "force_nva" in screen.clicks and "force_us" not in screen.clicks
    assert "switch_team" not in screen.clicks


def test_switches_to_the_short_team_once():
    # Rejoining skips Select Force; the game put us on NVA (the fake shows
    # its badge) while NVA is 6 ahead.
    config, game, screen, clock = make()
    path = dict(HAPPY_PATH)
    path["browser_join"] = ({"server_row", "browser_join", "browser_refresh"},
                            {"switch_team", "faction_nva", "squad_join", "infantry_create"})
    screen.transitions = path

    def fetch(_url):
        return ServerStatus("S", 20 if not screen.clicks.count("squad_join") else 80, 7, 13, 0)

    runner.seed(config, game, screen, fetch, clock)
    assert screen.clicks.count("switch_team") == 1
    assert screen.clicks.index("switch_team") < screen.clicks.index("squad_join")


def test_creates_a_squad_when_none_open():
    config, game, screen, clock = make()
    path = dict(HAPPY_PATH)
    path["browser_join"] = ({"server_row", "browser_join", "browser_refresh"}, {"switch_team", "infantry_create"})
    screen.transitions = path
    runner.seed(config, game, screen, statuses(10, 80), clock)
    assert "infantry_create" in screen.clicks


def test_restarts_after_crash():
    config, game, screen, clock = make()
    calls = {"n": 0}

    def fetch(_url):
        calls["n"] += 1
        if calls["n"] == 3:  # crash while seeding
            game.is_running = False
            screen.visible = set()
        return ServerStatus("S", 80 if calls["n"] >= 6 else 10, 5, 5, 0)

    assert runner.seed(config, game, screen, fetch, clock) is runner.Outcome.SEEDED
    assert game.launches == 2


def test_rejoins_after_kick_to_menu():
    config, game, screen, clock = make()
    calls = {"n": 0}

    def fetch(_url):
        calls["n"] += 1
        if calls["n"] == 3:
            screen.visible = {"menu_enlist"}
        return ServerStatus("S", 80 if calls["n"] >= 6 else 20, 10, 10, 0)

    assert runner.seed(config, game, screen, fetch, clock) is runner.Outcome.SEEDED
    assert screen.clicks.count("browser_join") == 2
    assert game.launches == 1


def test_redeploys_after_death_or_new_map():
    config, game, screen, clock = make()
    calls = {"n": 0}

    def fetch(_url):
        calls["n"] += 1
        if calls["n"] == 3:
            screen.visible = {"deploy_button"}
        return ServerStatus("S", 80 if calls["n"] >= 6 else 20, 10, 10, 0)

    assert runner.seed(config, game, screen, fetch, clock) is runner.Outcome.SEEDED
    assert screen.keys.count("f") == 3  # role, deploy, redeploy


def test_overlays_in_game_are_closed_without_leaving():
    config, game, screen, clock = make()
    calls = {"n": 0}

    def fetch(_url):
        calls["n"] += 1
        if calls["n"] == 3:
            screen.visible = {"admin_yes"}
        if calls["n"] == 5:
            screen.visible = {"game_menu_leave"}
        return ServerStatus("S", 80 if calls["n"] >= 8 else 20, 10, 10, 0)

    assert runner.seed(config, game, screen, fetch, clock) is runner.Outcome.SEEDED
    assert game.launches == 1 and game.closes == 1
    assert screen.clicks.count("admin_yes") == 2  # once while joining, once in game
    assert "esc" in screen.keys
    assert screen.keys.count("space") == 1  # only the splash, never in game


def test_no_input_while_game_is_not_in_front():
    config, game, screen, clock = make()
    game.focused = False
    config.max_minutes = 15
    runner.seed(config, game, screen, statuses(10), clock)
    assert screen.clicks == [] and screen.keys == [] and screen.typed == []


def test_crash_during_navigation_is_noticed_at_once():
    screen = FakeScreen(HAPPY_PATH)
    screen.visible = {"menu_enlist"}
    clock = FakeClock()
    alive = iter([True, True, False])
    nav = flow.Navigator(screen, Config(), clock, lambda: None, alive=lambda: next(alive))
    assert not nav.get_in(timeout=600)
    assert clock.now < 30


def test_refreshes_when_server_is_missing():
    screen = FakeScreen(HAPPY_PATH)
    screen.visible = {"browser_refresh"}
    clock = FakeClock()
    nav = flow.Navigator(screen, Config(), clock, lambda: None)
    assert not nav.get_in(timeout=100)
    assert 4 <= screen.keys.count("r") <= 6  # every ~20 s, not every tick


def test_tries_another_squad_when_one_is_full():
    screen = FakeScreen({})
    screen.visible = {"switch_team"}
    squads = [(100, 300), (100, 360)]
    screen.find_all = lambda name, region=None: squads if name == "squad_join" else []
    screen.find = lambda name, region=None: (200, 100) if name == "infantry_create" else None
    clicked = []
    screen.click = clicked.append
    nav = flow.Navigator(screen, Config(), FakeClock(), lambda: None)
    for _ in range(3):
        nav.handle("switch_team")
    # Each squad once (both full), then make our own.
    assert clicked == [(100, 300), (100, 360), (200, 100)]


def test_skips_when_pc_locked():
    config, game, screen, clock = make()
    game.locked = True
    assert runner.seed(config, game, screen, statuses(10), clock) is runner.Outcome.LOCKED
    assert game.launches == 0


def test_does_not_relaunch_near_the_time_limit():
    config, game, screen, clock = make()
    config.max_minutes = 20
    calls = {"n": 0}

    def fetch(_url):
        calls["n"] += 1
        if calls["n"] == 25:  # crash with ~7 minutes left, less than a relaunch needs
            game.is_running = False
        return ServerStatus("S", 20, 10, 10, 0)

    assert runner.seed(config, game, screen, fetch, clock) is runner.Outcome.TIMED_OUT
    assert game.launches == 1
    assert clock.now <= 20 * 60 + 60


def test_gave_up_watches_for_a_late_game_start():
    config, game, screen, clock = make(launch_ok=False)
    runner.seed(config, game, screen, statuses(10), clock)
    assert game.lingered == 90


def test_stop_closes_the_game():
    config, game, screen, clock = make()
    calls = {"n": 0}

    def fetch(_url):
        calls["n"] += 1
        if calls["n"] == 4:
            raise flow.Stopped()
        return ServerStatus("S", 20, 10, 10, 0)

    try:
        runner.seed(config, game, screen, fetch, clock)
    except flow.Stopped:
        pass
    assert not game.is_running


def test_gives_up_when_game_wont_start():
    config, game, screen, clock = make(launch_ok=False)
    assert runner.seed(config, game, screen, statuses(10), clock) is runner.Outcome.GAVE_UP
    assert game.launches == config.max_restarts + 1


def test_gives_up_when_server_never_appears():
    config, game, screen, clock = make()
    path = dict(HAPPY_PATH)
    path[("browser_search", "enter")] = ({"browser_search"}, set())  # search finds nothing
    screen.transitions = path
    assert runner.seed(config, game, screen, statuses(10), clock) is runner.Outcome.GAVE_UP
    assert not game.is_running


def test_times_out_and_closes_game():
    config, game, screen, clock = make()
    config.max_minutes = 10
    assert runner.seed(config, game, screen, statuses(10), clock) is runner.Outcome.TIMED_OUT
    assert not game.is_running


def test_nudges_to_avoid_idle_kick():
    config, game, screen, clock = make()
    runner.seed(config, game, screen, statuses(*([10] * 8), 80), clock)
    assert "a" in screen.keys and "d" in screen.keys


def test_unknown_screen_is_logged_with_a_screenshot(tmp_path, monkeypatch, caplog):
    import seeder.config

    monkeypatch.setattr(seeder.config, "app_dir", lambda: tmp_path)
    screen = FakeScreen(HAPPY_PATH)
    saved = []
    screen.save_screenshot = saved.append
    screen.visible = {"menu_enlist"}
    screen.transitions = {"menu_enlist": ({"menu_enlist"}, set())}  # leads to a screen we don't know
    nav = flow.Navigator(screen, Config(), FakeClock(), lambda: None)
    assert not nav.get_in(timeout=200)
    assert len(saved) == 1 and saved[0].parent == tmp_path / "debug"
    assert "unrecognised screen" in caplog.text
