"""How the game is started and found, through Steam or the Epic launcher."""

import json

import pytest

from seeder import game
from seeder.config import Config
from seeder.game import Game, detect_epic_app_name

HLLV = "3b51901c38644473a9cba942253b3a41:cc1ab2f4d934407c8f1e6463d9c1dbdf:d7361b7d6fa94097bcadeac4b1f785fb"
FORTNITE = [  # what the launcher listed on the test PC before HLL Vietnam was installed
    {"InstallLocation": "X:\\Epic Games\\Fortnite", "NamespaceId": "fn", "ItemId": "b619cf61a4144d67bd753dc990637e7c",
     "ArtifactId": "94bc5ec13f8f438c97fdbef3e9019e27", "AppName": "94bc5ec13f8f438c97fdbef3e9019e27"},
    {"InstallLocation": "X:\\Epic Games\\Fortnite", "NamespaceId": "fn", "ItemId": "4fe75bbc5a674f4f9b356b5c90567da5",
     "ArtifactId": "Fortnite", "AppName": "Fortnite"},
]


def vietnam(folder="X:\\Epic Games\\Hell_Let_Loose_Vietnam", app="d7361b7d6fa94097bcadeac4b1f785fb"):
    return {"InstallLocation": folder, "NamespaceId": "3b51901c38644473a9cba942253b3a41",
            "ItemId": "cc1ab2f4d934407c8f1e6463d9c1dbdf", "ArtifactId": app, "AppName": app}


@pytest.fixture
def installed(tmp_path):
    def write(*entries):
        path = tmp_path / "LauncherInstalled.dat"
        # The launcher writes tabs and a byte-order mark
        path.write_text(json.dumps({"InstallationList": list(entries)}, indent="\t"), encoding="utf-8-sig")
        return path
    return write


def test_finds_vietnam_in_epics_own_folder(installed):
    # Epic names the folder Hell_Let_Loose_Vietnam; the old check wanted "hellletloose" with only spaces removed
    assert detect_epic_app_name(installed(*FORTNITE, vietnam())) == HLLV


@pytest.mark.parametrize("folder", ["D:\\Games\\HLLV", "E:\\Epic\\Something Else"])
def test_finds_vietnam_by_its_app_name_in_any_folder(installed, folder):
    assert detect_epic_app_name(installed(*FORTNITE, vietnam(folder))) == HLLV


@pytest.mark.parametrize("folder", ["X:\\Epic Games\\Hell_Let_Loose_Vietnam", "C:\\Epic Games\\HellLetLooseVietnam",
                                    "D:\\Hell Let Loose - Vietnam"])
def test_falls_back_to_the_folder_name_if_the_app_name_changes(installed, folder):
    entry = vietnam(folder, app="0123456789abcdef0123456789abcdef")
    assert detect_epic_app_name(installed(*FORTNITE, entry)) == HLLV.replace(game.EPIC_APP_NAME, entry["AppName"])


def test_the_app_name_beats_another_entry_in_a_matching_folder(installed):
    extra = vietnam(app="ffffffffffffffffffffffffffffffff")  # e.g. extra content installed alongside
    assert detect_epic_app_name(installed(extra, vietnam())) == HLLV


def test_original_hell_let_loose_is_not_vietnam(installed):
    assert detect_epic_app_name(installed({**FORTNITE[1], "InstallLocation": "X:\\Epic Games\\HellLetLoose",
                                           "AppName": "Lacebark"})) == ""


def test_only_the_app_name_when_the_ids_are_missing(installed):
    entry = {"InstallLocation": "X:\\Epic Games\\Hell_Let_Loose_Vietnam", "AppName": "d7361b7d6fa94097bcadeac4b1f785fb"}
    assert detect_epic_app_name(installed(entry)) == "d7361b7d6fa94097bcadeac4b1f785fb"


@pytest.mark.parametrize("text", ["", "not json", "[]", '{"InstallationList": null}', '{"InstallationList": [1, null]}'])
def test_unreadable_install_list(tmp_path, text):
    path = tmp_path / "LauncherInstalled.dat"
    path.write_text(text)
    assert detect_epic_app_name(path) == ""


def test_not_installed(installed, tmp_path):
    assert detect_epic_app_name(installed(*FORTNITE)) == ""
    assert detect_epic_app_name(tmp_path / "missing.dat") == ""


def test_epic_launch_link_matches_epics_shortcuts(monkeypatch, installed):
    path = installed(*FORTNITE, vietnam())
    monkeypatch.setattr(game, "detect_epic_app_name", lambda: detect_epic_app_name(path))
    assert Game(Config(launcher="epic")).launch_uri() == (
        "com.epicgames.launcher://apps/3b51901c38644473a9cba942253b3a41%3Acc1ab2f4d934407c8f1e6463d9c1dbdf"
        "%3Ad7361b7d6fa94097bcadeac4b1f785fb?action=launch&silent=true")


@pytest.mark.parametrize("setting, link", [
    ("SomeApp", "SomeApp"),
    (HLLV, HLLV.replace(":", "%3A")),
    (" " + HLLV.replace(":", "%3A") + " ", HLLV.replace(":", "%3A")),  # copied from a shortcut: not encoded twice
])
def test_epic_app_name_from_settings_wins(monkeypatch, setting, link):
    monkeypatch.setattr(game, "detect_epic_app_name", lambda: pytest.fail("shouldn't look"))
    assert Game(Config(launcher="epic", epic_app_name=setting)).launch_uri() == (
        f"com.epicgames.launcher://apps/{link}?action=launch&silent=true")


def test_epic_without_the_game_installed(monkeypatch):
    monkeypatch.setattr(game, "detect_epic_app_name", lambda: "")
    with pytest.raises(RuntimeError, match="Couldn't find HLL Vietnam in the Epic launcher"):
        Game(Config(launcher="epic")).launch_uri()


def test_steam_launch_link():
    assert Game(Config()).launch_uri() == "steam://rungameid/3079210"


@pytest.mark.parametrize("process_name", ["HLLVietnam-Win64-Shipping.exe",
                                          "HLLVietnamEpicGamesStore-Win64-Shipping.exe", ""])
@pytest.mark.parametrize("running", ["HLLVietnam-Win64-Shipping.exe",  # Steam
                                     "HLLVietnamEpicGamesStore-Win64-Shipping.exe"])  # Epic
def test_finds_the_game_from_either_store(process_name, running):
    # Every saved config.json has Steam's name, and Epic's build runs under another one
    assert Game(Config(process_name=process_name))._matches(running)


@pytest.mark.parametrize("running", ["Launch_HLL.exe", "HLLVietnamEpicGamesStore.exe", "start_protected_game.exe",
                                     "HLL-Win64-Shipping.exe"])  # Epic's launcher stub, EAC, the original HLL
def test_launchers_and_other_games_are_not_the_game(running):
    assert not Game(Config())._matches(running)


def test_a_null_process_name_means_any_hll_build():
    assert Game(Config(process_name=None))._matches("HLLVietnamEpicGamesStore-Win64-Shipping.exe")


def test_a_custom_process_name_is_matched_exactly():
    game_ = Game(Config(process_name="Other-Win64-Shipping.exe"))
    assert game_._matches("other-win64-shipping.exe")
    assert not game_._matches("HLLVietnamEpicGamesStore-Win64-Shipping.exe")
