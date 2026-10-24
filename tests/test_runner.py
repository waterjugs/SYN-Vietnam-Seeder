from seeder import flow, runner
from seeder.config import Config
from seeder.crcon import ServerStatus

from .fakes import HAPPY_PATH, FakeClock, FakeGame, FakeScreen


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
    assert game.closes == 0 and screen.clicks == []


def test_joins_weaker_team_and_leaves_once_seeded():
    config, game, screen, clock = make()
    fetch = statuses(11, 11, 41, 79, 80)  # allies ahead by one
    assert runner.seed(config, game, screen, fetch, clock) is runner.Outcome.SEEDED
    assert screen.typed == ["Syndicate"]
    assert screen.clicks[:5] == ["menu_play", "browser_search", "server_row", "browser_join", "team_nva"]
    assert screen.clicks[5:7] == ["role_rifleman", "spawn_hq"]
    assert "deploy_button" in screen.clicks
    assert game.launches == 1 and not game.is_running


def test_picks_allies_when_they_are_short():
    config, game, screen, clock = make()
    runner.seed(config, game, screen, statuses(10, 80, allied_heavy=False), clock)
    assert "team_us" in screen.clicks and "team_nva" not in screen.clicks


def test_restarts_after_crash():
    config, game, screen, clock = make()
    calls = {"n": 0}
    base = statuses(10)

    def fetch(url):
        calls["n"] += 1
        if calls["n"] == 3:  # crash while seeding
            game.is_running = False
            screen.visible = set()
        return base(url) if calls["n"] < 6 else ServerStatus("S", 80, 40, 40, 0)

    assert runner.seed(config, game, screen, fetch, clock) is runner.Outcome.SEEDED
    assert game.launches == 2


def test_rejoins_after_kick_to_menu():
    config, game, screen, clock = make()
    calls = {"n": 0}

    def fetch(_url):
        calls["n"] += 1
        if calls["n"] == 3:
            screen.visible = {"menu_play"}
        return ServerStatus("S", 80 if calls["n"] >= 6 else 20, 10, 10, 0)

    assert runner.seed(config, game, screen, fetch, clock) is runner.Outcome.SEEDED
    assert screen.clicks.count("browser_join") == 2
    assert game.launches == 1


def test_gives_up_when_game_wont_start():
    config, game, screen, clock = make(launch_ok=False)
    assert runner.seed(config, game, screen, statuses(10), clock) is runner.Outcome.GAVE_UP
    assert game.launches == config.max_restarts + 1


def test_times_out_and_closes_game():
    config, game, screen, clock = make()
    config.max_minutes = 10
    assert runner.seed(config, game, screen, statuses(10), clock) is runner.Outcome.TIMED_OUT
    assert not game.is_running


def test_nudges_to_avoid_idle_kick():
    config, game, screen, clock = make()
    runner.seed(config, game, screen, statuses(*([10] * 8), 80), clock)
    assert "a" in screen.keys and "d" in screen.keys


def test_popup_is_dismissed_during_join():
    screen = FakeScreen({**HAPPY_PATH, "popup_ok": ({"popup_ok"}, {"menu_play"})})
    screen.visible = {"popup_ok"}
    assert flow.join_server(screen, Config(), FakeClock())
    assert screen.clicks[0] == "popup_ok"


def test_redeploys_on_new_map():
    screen = FakeScreen(HAPPY_PATH)
    screen.visible = {"team_us", "team_nva"}
    assert flow.deploy(screen, "allies", Config(), FakeClock(), first_timeout=10)
    assert screen.clicks == ["team_us", "role_rifleman", "spawn_hq", "deploy_button"]
