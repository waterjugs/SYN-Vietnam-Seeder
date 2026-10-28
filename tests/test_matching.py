"""Template matching against real HLL Vietnam screenshots (tests/screens,
captured 2026-10-24 at 2560x1440 and stored at 1920x1080)."""

from pathlib import Path

import cv2
import numpy as np
import pytest

from seeder import flow
from seeder.screen import Vision, bundled_templates_dir, load_templates, match_all, prepare_frame

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
    "select_role": "roles_confirm",  # 2026-10-26 live run: SELECT A ROLE after joining someone else's squad
    "deploy": "deploy_button",
    "deploy_counting": None,  # after F: CANCEL DEPLOY counting down; another F would cancel it
    "ingame": None,
    "gamemenu": "game_menu_leave",
}
RESOLUTIONS = {"1080p": (1920, 1080), "720p": (1280, 720), "1440p": (2560, 1440)}

# Captured natively at 1920x1080 on 2026-10-27 (live run on game build v1.7),
# named like the screenshots above. The game draws small text differently from
# 1440p here, which the resized screenshots above can't show: the 1440p server
# name and CREATE A UNIT crops alone scored 0.85 and 0.84.
EXPECTED_1080P = {
    "menu": "menu_enlist",
    "search": "server_row",
    "select_force": "select_force",
    "units": "switch_team",
    "create_unit": "create_unit",
    "deploy_counting": None,
    "ingame": None,
}


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


def load_1080p(name: str) -> np.ndarray:
    return cv2.imread(str(SCREENS / "1080p" / f"{name}.jpg"), cv2.IMREAD_GRAYSCALE)


@pytest.mark.parametrize("shot", EXPECTED_1080P)
def test_recognises_native_1080p_screen(shot):
    assert flow.current_screen(ImageScreen(load_1080p(shot))) == EXPECTED_1080P[shot]


@pytest.mark.parametrize("name, shot", [("server_row", "search"), ("create_unit", "create_unit")])
def test_native_1080p_text_crops_match_on_their_own(name, shot):
    # The 1440p crops also pass the lowered thresholds here, so check the 1080p
    # crop alone, at the default threshold: it fails if the crop goes missing,
    # is cut from the wrong box or is scaled as if cut at 1440p.
    crops = [t for t in load_templates(bundled_templates_dir())[name] if t[1] == 1080]
    assert crops, f"no {name}.1080p.png"
    assert match_all(prepare_frame(load_1080p(shot)), Vision({name: crops}).templates[name])


def test_native_1080p_join_on_server_row():
    screen = ImageScreen(load_1080p("search"))
    screen.refresh()
    row = screen.find("server_row")
    joins = screen.find_all("browser_join")
    assert row and joins
    # The only row: name at about (365, 227), JOIN at about (1294, 233).
    assert abs(row[0] - 365) < 15 and abs(row[1] - 227) < 15
    join = min(joins, key=lambda pos: abs(pos[1] - row[1]))
    assert abs(join[0] - 1294) < 15 and abs(join[1] - 233) < 15


def test_native_1080p_units_and_create_unit():
    units = ImageScreen(load_1080p("units"))
    units.refresh()
    plus = units.find("infantry_create", flow.INFANTRY_CREATE)
    assert plus and 0.29 * 1920 < plus[0] < 0.53 * 1920
    assert units.find("faction_nva", flow.FACTION_BADGE)  # this run picked NVA
    popup = ImageScreen(load_1080p("create_unit"))
    popup.refresh()
    button = popup.find("create_unit_button", flow.CREATE_UNIT_BUTTON)
    assert button and abs(button[0] / 1920 - 0.765) < 0.02 and abs(button[1] / 1080 - 0.741) < 0.02


def test_native_1080p_force_cards():
    screen = ImageScreen(load_1080p("select_force"))
    screen.refresh()
    us = screen.find(*flow.FORCE_CARDS["allies"])
    nva = screen.find(*flow.FORCE_CARDS["axis"])
    assert us and us[0] < 960
    assert nva and nva[0] > 960


@pytest.mark.parametrize("res", RESOLUTIONS)
def test_units_screen_details(res):
    w, h = RESOLUTIONS[res]
    screen = ImageScreen(load("units", (w, h)))
    screen.refresh()
    assert screen.find("faction_nva", flow.FACTION_BADGE)
    plus = screen.find("infantry_create", flow.INFANTRY_CREATE)
    assert plus and 0.29 * w < plus[0] < 0.53 * w


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
    assert templates["menu_enlist"][0][0].shape == (20, 50)
    assert len(templates["browser_join"]) == 1


def test_variants_named_after_a_height_are_scaled_from_it(tmp_path):
    img = np.full((30, 100), 200, np.uint8)
    for name in ("server_row.png", "server_row.1080p.png", "roles_confirm.title.png"):
        cv2.imwrite(str(tmp_path / name), img)
    templates = load_templates(tmp_path)
    assert sorted(height for _, height in templates["server_row"]) == [1080, 1440]
    assert [height for _, height in templates["roles_confirm"]] == [1440]
    # A 1080p crop is shrunk by 720/1080, a 1440p one by 720/1440.
    widths = sorted({needle.shape[1] for needle in Vision(templates).templates["server_row"]})
    assert widths == [48, 50, 52, 63, 67, 70]


def test_no_matches_on_noise():
    rng = np.random.default_rng(1)
    noise = rng.integers(0, 255, (720, 1280), dtype=np.uint8)
    templates = Vision(load_templates(bundled_templates_dir())).templates
    for name, needles in templates.items():
        assert match_all(noise, needles) == [], name
