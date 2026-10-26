"""Re-cuts templates/*.png from full 2560x1440 game screenshots.

    python tools/crop_templates.py <folder of screenshots>

The folder needs the screenshots named below (Steam's F12 saves them under
Steam/userdata/<id>/760/remote/3079210/screenshots). After a game patch,
retake the affected screen, adjust its box here if the layout moved, rerun,
then run the tests.
"""

import sys
from pathlib import Path

import cv2

# template: (screenshot, left, top, right, bottom) in 2560x1440 pixels
BOXES = {
    "menu_enlist": ("menu", 123, 890, 238, 921),
    "browser_search": ("browser", 1904, 184, 2082, 214),
    "server_row": ("search", 272, 288, 700, 318),
    "browser_join": ("search", 1641, 283, 1811, 339),
    "browser_refresh": ("browser", 282, 1336, 394, 1373),  # text only; the key icon matches other hints
    "switch_team": ("units", 345, 1215, 527, 1242),
    "faction_nva": ("units", 74, 1173, 184, 1283),
    "squad_join": ("units", 1268, 286, 1318, 336),
    "infantry_create": ("units", 1012, 216, 1092, 252),
    "roles_confirm": ("roles", 281, 1338, 459, 1372),
    "admin_yes": ("roles_msg", 2203, 598, 2302, 629),
    "deploy_button": ("deploy", 2110, 1301, 2317, 1343),
    "game_menu_leave": ("gamemenu", 123, 1150, 360, 1181),
    # select_force.jpg was pieced together from native-resolution zooms
    "select_force": ("select_force", 1037, 281, 1520, 340),
    "force_us": ("select_force", 421, 601, 789, 641),
    "force_nva": ("select_force", 2021, 601, 2128, 641),
}


def main(folder: Path) -> None:
    out = Path(__file__).resolve().parent.parent / "templates"
    for name, (shot, x0, y0, x1, y1) in BOXES.items():
        image = cv2.imread(str(folder / f"{shot}.jpg"))
        if image is None:
            print(f"skip {name}: no {shot}.jpg")
            continue
        if image.shape[:2] != (1440, 2560):
            sys.exit(f"{shot}.jpg must be 2560x1440")
        cv2.imwrite(str(out / f"{name}.png"), image[y0:y1, x0:x1])
        print(f"wrote {name}.png")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
