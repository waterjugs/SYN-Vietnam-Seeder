import cv2
import numpy as np

from seeder.screen import load_templates, match_template


def _button(width=120, height=40) -> np.ndarray:
    img = np.full((height, width), 30, np.uint8)
    cv2.rectangle(img, (2, 2), (width - 3, height - 3), 200, 2)
    cv2.putText(img, "PLAY", (22, 29), cv2.FONT_HERSHEY_SIMPLEX, 0.9, 255, 2)
    return img


def _screen_with(button: np.ndarray, at: tuple[int, int], size=(1080, 1920)) -> np.ndarray:
    rng = np.random.default_rng(0)
    screen = rng.integers(0, 60, size, dtype=np.uint8)
    x, y = at
    screen[y:y + button.shape[0], x:x + button.shape[1]] = button
    return screen


def test_finds_button_at_reference_resolution():
    button = _button()
    hit = match_template(_screen_with(button, (800, 500)), button, [1.0])
    assert hit is not None
    assert abs(hit[0] - 860) <= 2 and abs(hit[1] - 520) <= 2


def test_finds_button_on_1440p_screen():
    button = _button()
    scale = 1440 / 1080
    big = cv2.resize(button, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
    screen = _screen_with(big, (1000, 700), size=(1440, 2560))
    hit = match_template(screen, button, [scale * f for f in (0.95, 1.0, 1.05)])
    assert hit is not None
    assert abs(hit[0] - (1000 + big.shape[1] // 2)) <= 3


def test_no_false_match_on_noise():
    rng = np.random.default_rng(1)
    noise = rng.integers(0, 60, (1080, 1920), dtype=np.uint8)
    assert match_template(noise, _button(), [1.0]) is None


def test_user_templates_override_bundled(tmp_path):
    bundled, user = tmp_path / "bundled", tmp_path / "user"
    bundled.mkdir(), user.mkdir()
    cv2.imwrite(str(bundled / "menu_play.png"), _button())
    cv2.imwrite(str(bundled / "menu_play.alt.png"), _button())
    cv2.imwrite(str(bundled / "browser_join.png"), _button())
    cv2.imwrite(str(user / "menu_play.png"), _button(100, 30))
    templates = load_templates(bundled, user)
    assert len(templates["menu_play"]) == 1
    assert templates["menu_play"][0].shape == (30, 100)
    assert len(templates["browser_join"]) == 1
