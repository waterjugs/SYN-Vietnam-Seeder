import json

from seeder.config import Config


def test_round_trip(tmp_path):
    path = tmp_path / "config.json"
    Config(start_time="06:35", launcher="epic").save(path)
    loaded = Config.load(path)
    assert loaded.start_time == "06:35" and loaded.launcher == "epic"


def test_reads_file_saved_with_bom_and_ignores_unknown_keys(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"start_time": "08:00", "old_setting": 1}), encoding="utf-8-sig")
    assert Config.load(path).start_time == "08:00"


def test_missing_file_gives_defaults(tmp_path):
    assert Config.load(tmp_path / "nope.json") == Config()
