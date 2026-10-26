"""Template matching against real HLL Vietnam screenshots (tests/screens,
captured 2026-10-24 at 2560x1440 and stored at 1920x1080)."""

from pathlib import Path

import cv2
import numpy as np
import pytest

from seeder import flow
from seeder.screen import Vision, bundled_templates_dir, load_templates, match_all

SCREENS = Path(__file__).parent / "screens"

# Screenshot -> the screen flow.current_screen() should report.
EXPECTED = {
    "warn": None,  # splash, handled by pressing space
    "menu": "menu_enlist",
    "browser": "browser_search",
    "search": "server_row",
    "hover": "server_row",
    "search_empty": "browser_refresh",  # edited copy of "search" with the row removed
    "select_force": "select_force",  # assembled from native-res zooms of the live screen
    "units": "switch_team",
    "create_unit": "create_unit",  # popup after +; assembled from native-res zooms
    "roles_msg": "admin_yes",
    "roles": "roles_confirm",
    "roles_live": "roles_confirm",  # 2026-10-26 live run, half-res capture: other background behind "CONFIRM ROLE"
    "deploy": "deploy_button",
    "deploy_counting": None,  # after F: CANCEL DEPLOY counting down; another F would cancel it
    "ingame": None,
    "gamemenu": "game_menu_leave",
}
RESOLUTIONS = {"1080p": (1920, 1080), "720p": (1280, 720), "1440p": (2560, 1440)}


class ImageScreen(Vision):
    def __init__(self, image: np.ndarray):
        super().__init__(load_templates(bundled_templates_dir()))
        self.image = image

    def refresh(self):
        self.set_frame(self.image)


def load(name: str, size: tuple[int, int]) -> np.ndarray:
    gray = cv2.imread(str(SCREENS / f"{name}.jpg"), cv2.IMREAD_GRAYSCALE)
    return cv2.resize(gray, size, interpolation=cv2.INTER_AREA if size[0] < gray.shape[1] else cv2.INTER_CUBIC)


@pytest.mark.parametrize("res", RESOLUTIONS)
@pytest.mark.parametrize("shot", EXPECTED)
def test_recognises_screen(shot, res):
    screen = ImageScreen(load(shot, RESOLUTIONS[res]))
    assert flow.current_screen(screen) == EXPECTED[shot]


@pytest.mark.parametrize("res", RESOLUTIONS)
def test_units_screen_details(res):
    w, h = RESOLUTIONS[res]
    screen = ImageScreen(load("units", (w, h)))
    screen.refresh()
    assert screen.find("faction_nva", flow.FACTION_BADGE)
    squad = screen.find("squad_join", flow.INFANTRY_COLUMN)
    assert squad and 0.29 * w < squad[0] < 0.53 * w
    assert screen.find("infantry_create", flow.INFANTRY_CREATE)


@pytest.mark.parametrize("res", RESOLUTIONS)
def test_select_force_cards(res):
    w, h = RESOLUTIONS[res]
    screen = ImageScreen(load("select_force", (w, h)))
    screen.refresh()
    us = screen.find(*flow.FORCE_CARDS["allies"])
    nva = screen.find(*flow.FORCE_CARDS["axis"])
    assert us and us[0] < w / 2
    assert nva and nva[0] > w / 2


@pytest.mark.parametrize("res", RESOLUTIONS)
def test_create_unit_button(res):
    w, h = RESOLUTIONS[res]
    screen = ImageScreen(load("create_unit", (w, h)))
    screen.refresh()
    button = screen.find("create_unit_button", flow.CREATE_UNIT_BUTTON)
    # CREATE UNIT sits at about (0.765, 0.741) of the screen
    assert button and abs(button[0] / w - 0.765) < 0.02 and abs(button[1] / h - 0.741) < 0.02


@pytest.mark.parametrize("res", RESOLUTIONS)
def test_join_button_on_server_row(res):
    w, h = RESOLUTIONS[res]
    screen = ImageScreen(load("search", (w, h)))
    screen.refresh()
    row = screen.find("server_row")
    joins = screen.find_all("browser_join")
    assert row and joins
    join = min(joins, key=lambda pos: abs(pos[1] - row[1]))
    # Measured on the 1440p original: JOIN centre at (1726, 311).
    assert abs(join[0] - 1726 * w / 2560) < 10 * w / 1920
    assert abs(join[1] - 311 * h / 1440) < 10 * h / 1080


def test_full_browser_has_many_join_buttons():
    screen = ImageScreen(load("browser", (1920, 1080)))
    screen.refresh()
    assert len(screen.find_all("browser_join")) >= 8


def test_clicks_map_back_to_screen_pixels():
    screen = ImageScreen(load("menu", (2560, 1440)))
    screen.refresh()
    x, y = screen.find("menu_enlist")
    assert abs(x - 180) < 12 and abs(y - 905) < 12  # measured on the original


def test_user_templates_override_bundled(tmp_path):
    bundled, user = tmp_path / "bundled", tmp_path / "user"
    bundled.mkdir(), user.mkdir()
    img = np.full((30, 100), 200, np.uint8)
    cv2.imwrite(str(bundled / "menu_enlist.png"), img)
    cv2.imwrite(str(bundled / "menu_enlist.alt.png"), img)
    cv2.imwrite(str(bundled / "browser_join.png"), img)
    cv2.imwrite(str(user / "menu_enlist.png"), img[:20, :50])
    templates = load_templates(bundled, user)
    assert len(templates["menu_enlist"]) == 1
    assert templates["menu_enlist"][0].shape == (20, 50)
    assert len(templates["browser_join"]) == 1


def test_no_matches_on_noise():
    rng = np.random.default_rng(1)
    noise = rng.integers(0, 255, (720, 1280), dtype=np.uint8)
    templates = Vision(load_templates(bundled_templates_dir())).templates
    for name, needles in templates.items():
        assert match_all(noise, needles) == [], name
