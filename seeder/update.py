"""Keeping SynSeeder up to date from its GitHub releases.

Only official release builds update themselves: CI writes assets/release.txt
into the exe when it builds a v* tag, so a preview built on a PC stays the
version it is. Before each seeding run, a release build asks GitHub for the
latest release and, if that's newer, downloads its SynSeeder.exe next to
itself as SynSeeder-update.exe.

A running exe can't be overwritten, and renaming it out of the way isn't
safe either: a PyInstaller exe keeps reading its own file for code it hasn't
loaded yet, and would then read the new exe instead. So the new version
finishes the job. The old one lets go of the seeding lock and starts
``SynSeeder-update.exe --install-to <old exe> --old-pid <pid> --seed``; once
the new one has the lock, the old one exits. The new one waits for the old
processes to end, copies itself over the old file and carries on with the
run. If something else still has the file open, such as a SynSeeder window
started from it, the new one keeps trying in the background during the run,
and keeps SynSeeder-update.exe so the next run can hand over again without
downloading it again.

A release that fails to start three times is skipped until a newer one is
out, so a bad release can't hold up every run.
"""

from __future__ import annotations

import contextlib
import ctypes
import hashlib
import json
import logging
import os
import re
import shutil
import sys
import threading
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import __version__, instance
from .config import app_dir

log = logging.getLogger(__name__)

LATEST_RELEASE = "https://api.github.com/repos/waterjugs/SYN-Vietnam-Seeder/releases/latest"
ASSET_NAME = "SynSeeder.exe"
UPDATE_NAME = "SynSeeder-update.exe"
FAILURES_NAME = "update-failed.json"  # in app_dir(): the release that last failed to start, and how often
MAX_FAILURES = 3
HANDOVER_SECONDS = 120  # for the new version to start; antivirus can take a while over a new exe
EXIT_SECONDS = 60  # for the old version to exit once the new one has the lock
REPLACE_TRIES = 5  # a second apart, once the old version has exited
RETRY_SECONDS = 30  # between tries in the background after that

Version = tuple[int, int, int]


@dataclass(frozen=True)
class Release:
    tag: str
    version: Version
    url: str
    size: int
    sha256: str  # hex; empty if GitHub didn't give a checksum


def parse_version(text: str) -> Version | None:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", text.strip())
    return (int(match[1]), int(match[2]), int(match[3])) if match else None


def current_version() -> Version:
    return parse_version(__version__) or (0, 0, 0)


def release_build() -> bool:
    """True in an exe CI built from a v* tag; only those update themselves."""
    base = getattr(sys, "_MEIPASS", None)
    return bool(getattr(sys, "frozen", False) and base and (Path(base) / "assets" / "release.txt").is_file())


def parse_release(payload: dict) -> Release | None:
    """The release's SynSeeder.exe, or None if it has none or isn't a final release."""
    if payload.get("draft") or payload.get("prerelease"):
        return None
    tag = str(payload.get("tag_name") or "")
    version = parse_version(tag)
    asset = next((a for a in payload.get("assets") or []
                  if a.get("name") == ASSET_NAME and a.get("state", "uploaded") == "uploaded"), None)
    if version is None or asset is None:
        return None
    url = str(asset.get("browser_download_url") or "")
    if not url.startswith("https://"):
        return None
    digest = str(asset.get("digest") or "")
    return Release(tag, version, url, int(asset.get("size") or 0),
                   digest.removeprefix("sha256:").lower() if digest.startswith("sha256:") else "")


def _get(url: str, accept: str, timeout: float):
    request = urllib.request.Request(url, headers={"User-Agent": f"SynSeeder/{__version__}", "Accept": accept})
    return urllib.request.urlopen(request, timeout=timeout)


def latest(url: str = LATEST_RELEASE, opener=_get, timeout: float = 15) -> Release | None:
    """The latest release, or None if GitHub can't be reached or the release has no exe."""
    try:
        with opener(url, "application/vnd.github+json", timeout) as response:
            return parse_release(json.load(response))
    except Exception as exc:  # network, HTTP or payload errors all mean "no update today"
        log.warning("Couldn't check for updates: %s", exc)
        return None


def download(release: Release, dest: Path, opener=_get, timeout: float = 30) -> bool:
    """Downloads the release's exe to ``dest`` and checks it. False, leaving no file, if anything is off."""
    part = dest.with_name(dest.name + ".part")
    digest, size, head = hashlib.sha256(), 0, b""
    try:
        with opener(release.url, "application/octet-stream", timeout) as response, open(part, "wb") as out:
            while chunk := response.read(1 << 20):
                head = (head + chunk)[:2]
                digest.update(chunk)
                size += len(chunk)
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        if head != b"MZ":
            raise ValueError("it isn't a Windows program")
        if release.size and size != release.size:
            raise ValueError(f"got {size} bytes, expected {release.size}")
        if release.sha256 and digest.hexdigest() != release.sha256:
            raise ValueError("its checksum doesn't match")
        os.replace(part, dest)
        return True
    except Exception as exc:
        log.warning("Couldn't download %s: %s", release.tag, exc)
        with contextlib.suppress(OSError):
            part.unlink()
        return False


def downloaded(release: Release, path: Path) -> bool:
    """True if an earlier run already downloaded this release's exe to ``path``."""
    if not release.sha256:
        return False
    try:
        with open(path, "rb") as f:
            return hashlib.file_digest(f, "sha256").hexdigest() == release.sha256
    except OSError:
        return False


def cleanup(folder: Path) -> None:
    """Deletes half-finished downloads and installs an earlier run left next to the exe."""
    for name in (UPDATE_NAME + ".part", ASSET_NAME + ".new"):
        _remove(folder / name)


def _remove(path: Path) -> None:
    with contextlib.suppress(OSError):
        path.unlink()


def failures(tag: str) -> int:
    """How many times this release has failed to start."""
    try:
        record = json.loads((app_dir() / FAILURES_NAME).read_text(encoding="utf-8"))
        return int(record["failures"]) if record["tag"] == tag else 0
    except (OSError, ValueError, KeyError, TypeError):
        return 0


def record_failure(tag: str) -> None:
    with contextlib.suppress(OSError):
        (app_dir() / FAILURES_NAME).write_text(json.dumps({"tag": tag, "failures": failures(tag) + 1}),
                                               encoding="utf-8")


def update_and_hand_over(config, args: list[str]) -> bool:
    """Before a run: if a newer release is out, downloads it and lets it take over.

    True means the new version has taken over the run and this process
    should exit without seeding; False means carry on with this version.
    """
    if not release_build():
        return False
    exe = Path(sys.executable)
    new = exe.with_name(UPDATE_NAME)
    cleanup(exe.parent)
    release = latest() if config.auto_update else None
    if release is None or release.version <= current_version():
        _remove(new)
        return False
    if failures(release.tag) >= MAX_FAILURES:
        log.warning("Skipping %s: it failed to start %s times. A newer release will be tried.",
                    release.tag, MAX_FAILURES)
        _remove(new)
        return False
    log.info("Updating from v%s to %s", __version__, release.tag)
    if not (downloaded(release, new) or download(release, new)):
        return False
    if hand_over(new, exe, release.tag, args):
        return True
    record_failure(release.tag)
    return False


def hand_over(new: Path, exe: Path, tag: str, args: list[str], instance=instance, clock=time) -> bool:
    """Starts the new exe to install itself over ``exe`` and take over this run.

    True once it has taken the seeding lock. False if it didn't start; then
    this process has the lock back and carries on as it is.
    """
    old = [arg for pid in instance.own_pids() for arg in ("--old-pid", str(pid))]
    instance.release()
    proc = None
    try:
        proc = instance.spawn_detached([str(new), "--install-to", str(exe), *old, *args])
        deadline = clock.monotonic() + HANDOVER_SECONDS
        while clock.monotonic() < deadline and proc.poll() is None:
            if instance.held_elsewhere():
                log.info("%s has taken over this run", tag)
                return True
            clock.sleep(0.5)
        log.warning("%s didn't start (exit code %s); carrying on with v%s", tag, proc.poll(), __version__)
    except Exception as exc:  # whatever happens, this process must get the lock back
        log.warning("Couldn't start %s: %s", tag, exc)
    if proc is not None and proc.poll() is None:
        instance.end_tree(proc.pid)
    _remove(new)
    if not instance.claim():
        log.info("Another seeding run started meanwhile; leaving it to that one")
        return True
    return False


def install(target: Path, old_pids: list[int], clock=time, instance=instance) -> bool:
    """Run by the new version that hand_over() started: copies this exe over ``target``.

    Waits for the old version's processes to end, since Windows won't
    replace a running exe. If something else still has the file open, it
    returns False and keeps trying in the background for the rest of the
    run; a later run hands over again if this one never managed.
    """
    temp = target.with_name(target.name + ".new")
    try:
        with open(sys.executable, "rb") as source, open(temp, "wb") as out:
            shutil.copyfileobj(source, out, 1 << 20)
            out.flush()
            os.fsync(out.fileno())  # on disk before it replaces the only working copy
    except OSError as exc:
        log.warning("Couldn't copy the update into place: %s", exc)
        _remove(temp)
        return False
    instance.wait_for_exit(old_pids, EXIT_SECONDS)
    if replace(temp, target, REPLACE_TRIES, 1, clock):
        return True
    log.warning("Couldn't replace %s yet; something has it open, maybe a SynSeeder window started from it. "
                "Trying again every %s s during this run.", target, RETRY_SECONDS)
    threading.Thread(target=replace, args=(temp, target, None, RETRY_SECONDS, clock), daemon=True).start()
    return False


def replace(temp: Path, target: Path, tries: int | None, wait: float, clock=time) -> bool:
    """Moves ``temp`` over ``target``, trying ``tries`` times (None: until it works)."""
    attempt = 0
    while True:
        attempt += 1
        try:
            os.replace(temp, target)
        except OSError as exc:
            if tries is not None and attempt >= tries:
                log.info("Couldn't replace %s: %s", target, exc)
                return False
            clock.sleep(wait)
        else:
            log.info("Installed v%s", __version__)
            return True


class VS_FIXEDFILEINFO(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in (
        "dwSignature", "dwStrucVersion", "dwFileVersionMS", "dwFileVersionLS", "dwProductVersionMS",
        "dwProductVersionLS", "dwFileFlagsMask", "dwFileFlags", "dwFileOS", "dwFileType", "dwFileSubtype",
        "dwFileDateMS", "dwFileDateLS")]


def file_version(path: Path) -> Version | None:
    """The version in a Windows program's properties (SynSeeder.spec sets it), or None."""
    if os.name != "nt":
        return None
    from ctypes import wintypes

    try:
        dll = ctypes.WinDLL("version")  # own copy, own prototypes
        dll.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
        dll.GetFileVersionInfoSizeW.restype = wintypes.DWORD
        dll.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
        dll.GetFileVersionInfoW.restype = wintypes.BOOL
        dll.VerQueryValueW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p),
                                       ctypes.POINTER(wintypes.UINT)]
        dll.VerQueryValueW.restype = wintypes.BOOL
        size = dll.GetFileVersionInfoSizeW(str(path), None)
        if not size:
            return None
        data = ctypes.create_string_buffer(size)
        info, length = ctypes.c_void_p(), wintypes.UINT()
        if not dll.GetFileVersionInfoW(str(path), 0, size, data) or not dll.VerQueryValueW(
                data, "\\", ctypes.byref(info), ctypes.byref(length)) or not info.value:
            return None
        fixed = ctypes.cast(info, ctypes.POINTER(VS_FIXEDFILEINFO)).contents
    except (AttributeError, OSError, ctypes.ArgumentError):
        return None
    return fixed.dwFileVersionMS >> 16, fixed.dwFileVersionMS & 0xFFFF, fixed.dwFileVersionLS >> 16
