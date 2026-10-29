import hashlib
import io
import json
import os
import sys
import types

import pytest

from seeder import __main__ as main_module
from seeder import instance, schedule, update
from seeder.config import Config

from .fakes import FakeClock

EXE = b"MZ" + b"\0" * 1000


def payload(tag="v1.2.0", data=EXE, **extra):
    """The parts of GitHub's latest-release answer that the updater reads."""
    asset = {
        "name": "SynSeeder.exe",
        "state": "uploaded",
        "size": len(data),
        "digest": "sha256:" + hashlib.sha256(data).hexdigest(),
        "browser_download_url": f"https://github.com/waterjugs/SYN-Vietnam-Seeder/releases/download/{tag}/SynSeeder.exe",
    }
    asset.update(extra)
    return {"tag_name": tag, "draft": False, "prerelease": False, "assets": [{"name": "notes.txt"}, asset]}


def serving(data: bytes):
    """An opener that answers every request with ``data``."""
    return lambda url, accept, timeout: io.BytesIO(data)


def test_parse_version():
    assert update.parse_version("v1.2.3") == (1, 2, 3)
    assert update.parse_version("1.10.0") == (1, 10, 0)
    assert update.parse_version("v1.2") is None
    assert update.parse_version("v1.2.3-beta") is None


def test_parse_release_reads_the_exe_asset():
    release = update.parse_release(payload())
    assert release.tag == "v1.2.0" and release.version == (1, 2, 0)
    assert release.url.endswith("/v1.2.0/SynSeeder.exe")
    assert release.size == len(EXE) and release.sha256 == hashlib.sha256(EXE).hexdigest()


def test_parse_release_without_a_checksum():
    assert update.parse_release(payload(digest=None)).sha256 == ""


@pytest.mark.parametrize("change", [
    {"prerelease": True},
    {"draft": True},
    {"tag_name": "latest"},
    {"assets": [{"name": "notes.txt"}]},
])
def test_parse_release_skips_what_it_cant_install(change):
    assert update.parse_release({**payload(), **change}) is None


def test_parse_release_skips_an_exe_still_uploading_or_not_https():
    assert update.parse_release(payload(state="starter")) is None
    assert update.parse_release(payload(browser_download_url="http://example.com/SynSeeder.exe")) is None


def test_latest_reads_github():
    assert update.latest(opener=serving(json.dumps(payload()).encode())).version == (1, 2, 0)


def test_latest_is_none_when_github_cant_be_reached():
    def fail(url, accept, timeout):
        raise OSError("no network")

    assert update.latest(opener=fail) is None
    assert update.latest(opener=serving(b"<html>rate limited</html>")) is None


def test_download_checks_and_keeps_a_good_file(tmp_path):
    dest = tmp_path / update.UPDATE_NAME
    assert update.download(update.parse_release(payload()), dest, opener=serving(EXE))
    assert dest.read_bytes() == EXE
    assert sorted(p.name for p in tmp_path.iterdir()) == [update.UPDATE_NAME]


@pytest.mark.parametrize("served", [
    EXE[:-1],  # cut short
    EXE[:-1] + b"x",  # same size, different bytes
    b"<html>" + EXE[6:],  # not a program at all
])
def test_download_throws_away_a_bad_file(tmp_path, served):
    dest = tmp_path / update.UPDATE_NAME
    assert not update.download(update.parse_release(payload()), dest, opener=serving(served))
    assert list(tmp_path.iterdir()) == []


def test_download_survives_a_dropped_connection(tmp_path):
    class Dropped(io.BytesIO):
        def read(self, size=-1):
            raise ConnectionResetError("dropped")

    dest = tmp_path / update.UPDATE_NAME
    assert not update.download(update.parse_release(payload()), dest, opener=lambda *a: Dropped(EXE))
    assert list(tmp_path.iterdir()) == []


def test_cleanup_removes_leftovers_only(tmp_path):
    for name in ("SynSeeder.exe", "SynSeeder-update.exe", "SynSeeder-update.exe.part", "SynSeeder.exe.new"):
        (tmp_path / name).write_bytes(EXE)
    update.cleanup(tmp_path)
    assert [p.name for p in tmp_path.iterdir()] == ["SynSeeder.exe"]


# Deciding whether to update

@pytest.fixture
def installed(tmp_path, monkeypatch):
    """A release build of v1.0.0 installed in tmp_path; records what the updater does."""
    exe = tmp_path / "SynSeeder.exe"
    exe.write_bytes(EXE)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(update, "__version__", "1.0.0")
    monkeypatch.setattr(update, "release_build", lambda: True)
    calls = []
    monkeypatch.setattr(update, "latest", lambda: calls.append("latest") or update.parse_release(payload()))

    def download(release, dest):
        calls.append(("download", release.tag, dest.name))
        dest.write_bytes(EXE)
        return True

    monkeypatch.setattr(update, "download", download)
    monkeypatch.setattr(update, "hand_over", lambda new, exe, tag, args: calls.append(("hand_over", new.name, tag,
                                                                                          args)) or True)
    return calls


def test_a_newer_release_takes_over(installed):
    assert update.update_and_hand_over(Config(), ["--seed"])
    assert installed == ["latest", ("download", "v1.2.0", "SynSeeder-update.exe"),
                         ("hand_over", "SynSeeder-update.exe", "v1.2.0", ["--seed"])]


def test_same_or_older_release_does_nothing(installed, monkeypatch):
    monkeypatch.setattr(update, "__version__", "1.2.0")
    assert not update.update_and_hand_over(Config(), ["--seed"])
    assert installed == ["latest"]


def test_switched_off_in_settings(installed):
    assert not update.update_and_hand_over(Config(auto_update=False), ["--seed"])
    assert installed == []


def test_builds_that_arent_releases_never_update(installed, monkeypatch):
    monkeypatch.setattr(update, "release_build", lambda: False)
    assert not update.update_and_hand_over(Config(), ["--seed"])
    assert installed == []


def test_running_from_source_is_not_a_release_build():
    assert not update.release_build()


# Handing the run over to the new version

class FakeProc:
    pid = 4242

    def __init__(self, exits_after=None, code=1):
        self.polls = 0
        self.exits_after = exits_after
        self.code = code

    def poll(self):
        self.polls += 1
        return self.code if self.exits_after is not None and self.polls > self.exits_after else None


class FakeInstance:
    """The seeding lock and process starting, as hand_over() uses them."""

    def __init__(self, proc=None, takes_lock_after=None, spawn_error=None, free_at_end=True):
        self.proc = proc or FakeProc()
        self.takes_lock_after = takes_lock_after
        self.spawn_error = spawn_error
        self.free_at_end = free_at_end
        self.events = []
        self.checks = 0

    def release(self):
        self.events.append("release")

    def claim(self):
        self.events.append("claim")
        return self.free_at_end

    def spawn_detached(self, command):
        self.events.append(("spawn", command))
        if self.spawn_error:
            raise self.spawn_error
        return self.proc

    def held_elsewhere(self):
        self.checks += 1
        return self.takes_lock_after is not None and self.checks > self.takes_lock_after

    def end_tree(self, pid):
        self.events.append(("end_tree", pid))


def hand_over(tmp_path, fake, clock=None):
    new = tmp_path / update.UPDATE_NAME
    new.write_bytes(EXE)
    exe = tmp_path / "SynSeeder.exe"
    taken = update.hand_over(new, exe, "v1.2.0", ["--seed", "--max-minutes", "5"], instance=fake,
                             clock=clock or FakeClock())
    return taken, new


def test_hand_over_when_the_new_version_takes_the_lock(tmp_path):
    fake = FakeInstance(takes_lock_after=3)
    taken, new = hand_over(tmp_path, fake)
    assert taken
    assert fake.events == ["release", ("spawn", [str(new), "--install-to", str(tmp_path / "SynSeeder.exe"),
                                                 "--seed", "--max-minutes", "5"])]
    assert new.exists()  # it's running; the next run deletes it


def test_hand_over_falls_back_when_the_new_version_exits(tmp_path):
    fake = FakeInstance(proc=FakeProc(exits_after=2))
    taken, new = hand_over(tmp_path, fake)
    assert not taken
    assert fake.events[-1] == "claim" and not any(e[0] == "end_tree" for e in fake.events if isinstance(e, tuple))
    assert not new.exists()


def test_hand_over_gives_up_on_a_new_version_that_hangs(tmp_path):
    fake = FakeInstance()
    clock = FakeClock()
    taken, new = hand_over(tmp_path, fake, clock)
    assert not taken
    assert clock.now >= update.HANDOVER_SECONDS
    assert fake.events[-2:] == [("end_tree", 4242), "claim"]


def test_hand_over_falls_back_when_the_new_version_cant_start(tmp_path):
    fake = FakeInstance(spawn_error=OSError("blocked by antivirus"))
    taken, new = hand_over(tmp_path, fake)
    assert not taken and fake.events[-1] == "claim"
    assert not new.exists()


def test_hand_over_lets_a_late_new_version_keep_the_run(tmp_path):
    fake = FakeInstance(proc=FakeProc(exits_after=0), free_at_end=False)
    taken, _ = hand_over(tmp_path, fake)
    assert taken


# The new version installing itself

def test_install_waits_for_the_old_exe_to_come_free(tmp_path, monkeypatch):
    me = tmp_path / update.UPDATE_NAME
    me.write_bytes(b"MZ new")
    target = tmp_path / "SynSeeder.exe"
    target.write_bytes(b"MZ old")
    monkeypatch.setattr(sys, "executable", str(me))
    real_replace, attempts = os.replace, []

    def replace(src, dst):
        attempts.append(dst)
        if len(attempts) < 4:
            raise PermissionError("the old version is still running")
        real_replace(src, dst)

    monkeypatch.setattr(update.os, "replace", replace)
    assert update.install(target, clock=FakeClock())
    assert target.read_bytes() == b"MZ new" and len(attempts) == 4
    assert sorted(p.name for p in tmp_path.iterdir()) == ["SynSeeder-update.exe", "SynSeeder.exe"]


def test_install_gives_up_and_leaves_the_old_exe(tmp_path, monkeypatch):
    me = tmp_path / update.UPDATE_NAME
    me.write_bytes(b"MZ new")
    target = tmp_path / "SynSeeder.exe"
    target.write_bytes(b"MZ old")
    monkeypatch.setattr(sys, "executable", str(me))

    def replace(src, dst):
        raise PermissionError("still running")

    monkeypatch.setattr(update.os, "replace", replace)
    clock = FakeClock()
    assert not update.install(target, clock=clock)
    assert clock.now >= update.INSTALL_SECONDS
    assert target.read_bytes() == b"MZ old"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["SynSeeder-update.exe", "SynSeeder.exe"]


# The seeding run

@pytest.fixture
def seeding(monkeypatch):
    """Stands in for the game side of run_seed(); lists the runs that got as far as seeding."""
    import seeder
    from seeder import runner
    from seeder import screen as screen_module

    winapi = types.SimpleNamespace(listen_for_stop_hotkey=lambda stop: None)
    monkeypatch.setitem(sys.modules, "seeder.winapi", winapi)
    monkeypatch.setattr(seeder, "winapi", winapi, raising=False)
    monkeypatch.setattr(screen_module, "Screen", lambda rect: None)
    runs = []
    monkeypatch.setattr(runner, "seed", lambda *args: runs.append(args) or runner.Outcome.SEEDED)
    monkeypatch.setattr(instance, "claim", lambda: True)
    return runs


def test_a_run_that_hands_over_does_no_seeding(seeding, monkeypatch):
    monkeypatch.setattr(update, "update_and_hand_over", lambda config, args: True)
    assert main_module.run_seed(Config(), ["--seed"]) == 0
    assert seeding == []


def test_a_run_with_nothing_to_update_seeds(seeding, monkeypatch):
    monkeypatch.setattr(update, "update_and_hand_over", lambda config, args: False)
    assert main_module.run_seed(Config(), ["--seed"]) == 0
    assert len(seeding) == 1


def test_a_broken_update_check_doesnt_stop_the_run(seeding, monkeypatch):
    def broken(config, args):
        raise RuntimeError("bug in the updater")

    monkeypatch.setattr(update, "update_and_hand_over", broken)
    assert main_module.run_seed(Config(), ["--seed"]) == 0
    assert len(seeding) == 1


def test_the_new_version_installs_itself_instead_of_checking(seeding, monkeypatch, tmp_path):
    installs = []
    monkeypatch.setattr(update, "install", installs.append)
    monkeypatch.setattr(update, "update_and_hand_over", lambda config, args: pytest.fail("checked for updates"))
    target = tmp_path / "SynSeeder.exe"
    assert main_module.run_seed(Config(), ["--install-to", str(target), "--seed"], install_to=str(target)) == 0
    assert installs == [target] and len(seeding) == 1


def test_main_passes_its_arguments_on(monkeypatch):
    seen = []
    monkeypatch.setattr(main_module, "setup_logging", lambda: None)
    monkeypatch.setattr(main_module, "run_seed", lambda config, args, install_to: seen.append((args, install_to)))
    main_module.main(["--seed", "--max-minutes", "5"])
    main_module.main(["--install-to", r"C:\x\SynSeeder.exe", "--seed"])
    assert seen == [(["--seed", "--max-minutes", "5"], None),
                    (["--install-to", r"C:\x\SynSeeder.exe", "--seed"], r"C:\x\SynSeeder.exe")]


# Starting processes and keeping the installed copy

def test_spawned_runs_unpack_themselves_afresh(monkeypatch):
    seen = {}

    def popen(command, **kwargs):
        seen.update(kwargs, command=command)
        return "proc"

    monkeypatch.setattr(instance.subprocess, "Popen", popen)
    assert instance.spawn_detached(["SynSeeder.exe", "--seed"]) == "proc"
    assert seen["command"] == ["SynSeeder.exe", "--seed"]
    assert seen["env"]["PYINSTALLER_RESET_ENVIRONMENT"] == "1"


@pytest.fixture
def frozen(tmp_path, monkeypatch):
    """A built exe of v1.0.0 run from Downloads, with %LOCALAPPDATA%\\SynSeeder in tmp_path."""
    download = tmp_path / "Downloads" / "SynSeeder.exe"
    download.parent.mkdir()
    download.write_bytes(b"MZ download")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(download))
    monkeypatch.setattr(schedule, "install_dir", lambda: tmp_path / "SynSeeder")
    monkeypatch.setattr(update, "__version__", "1.0.0")
    return tmp_path / "SynSeeder" / "SynSeeder.exe"


def test_first_install_copies_the_download(frozen):
    program, arguments = schedule.seed_command()
    assert program == str(frozen) and arguments == "--seed"
    assert frozen.read_bytes() == b"MZ download"


@pytest.mark.parametrize("installed_version, replaced", [((1, 1, 0), False), ((1, 0, 0), True), ((0, 9, 0), True),
                                                         (None, True)])
def test_an_older_download_never_replaces_an_updated_install(frozen, monkeypatch, installed_version, replaced):
    frozen.parent.mkdir()
    frozen.write_bytes(b"MZ installed")
    monkeypatch.setattr(update, "file_version", lambda path: installed_version)
    schedule.seed_command()
    assert frozen.read_bytes() == (b"MZ download" if replaced else b"MZ installed")


def test_file_version_reads_windows_program_properties(tmp_path):
    assert update.file_version(tmp_path / "missing.exe") is None
    if os.name == "nt":
        assert update.file_version(sys.executable)[:2] == sys.version_info[:2]
    else:
        assert update.file_version(sys.executable) is None
