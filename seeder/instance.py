"""Making sure only one seeding run happens at a time, and starting and stopping one."""

from __future__ import annotations

import logging
import os
import subprocess

import psutil

log = logging.getLogger(__name__)

MUTEX_NAME = "Local\\SynSeederSeeding"
ERROR_ALREADY_EXISTS = 183
SYNCHRONIZE = 0x00100000
DETACHED = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
_held = None


def claim() -> bool:
    """True if this process may seed; False if another run already is.

    Holds a named mutex until release() or the process ends. Always True off Windows.
    """
    global _held
    if os.name != "nt":
        return True
    import ctypes

    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return False
    _held = handle
    return True


def release() -> None:
    """Lets go of the lock claim() took, so another process can take over the run."""
    global _held
    if _held is not None:
        import ctypes

        ctypes.windll.kernel32.CloseHandle(_held)  # type: ignore[attr-defined]
        _held = None


def held_elsewhere() -> bool:
    """True if another process holds the lock. Meaningful only while this one doesn't."""
    if os.name != "nt":
        return False
    import ctypes

    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    handle = kernel32.OpenMutexW(SYNCHRONIZE, False, MUTEX_NAME)
    if not handle:
        return False
    kernel32.CloseHandle(handle)
    return True


def spawn_detached(command: list[str]) -> subprocess.Popen:
    """Starts a program that keeps running after this one exits.

    PYINSTALLER_RESET_ENVIRONMENT makes a SynSeeder.exe unpack itself
    afresh. Without it, an exe at the same path as this one would reuse
    this process's unpacked files, which are deleted when this one exits.
    """
    env = {**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"}
    return subprocess.Popen(command, creationflags=DETACHED if os.name == "nt" else 0, close_fds=True, env=env)


def end_tree(pid: int) -> None:
    """Ends a process and its children: a SynSeeder.exe is a launcher with the app as its child."""
    try:
        parent = psutil.Process(pid)
        procs = [*parent.children(recursive=True), parent]
    except psutil.Error:
        return
    for proc in procs:
        try:
            proc.kill()
        except psutil.Error:
            pass
    psutil.wait_procs(procs, timeout=10)


def seeding_processes() -> list[psutil.Process]:
    """Other processes running a seed (SynSeeder.exe --seed or python -m seeder --seed)."""
    me = os.getpid()
    found = []
    for proc in psutil.process_iter(["pid", "cmdline"]):
        cmd = proc.info["cmdline"] or []
        if proc.info["pid"] == me or "--seed" not in cmd:
            continue
        joined = " ".join(cmd).lower()
        if "synseeder" in joined or "-m seeder" in joined:
            found.append(proc)
    return found


def stop_seeding() -> bool:
    """Ends any running seed. Returns True if there was one."""
    procs = seeding_processes()
    for proc in procs:
        try:
            proc.terminate()
        except psutil.Error:
            pass
    psutil.wait_procs(procs, timeout=10)
    if procs:
        log.info("Stopped %s seeding process(es)", len(procs))
    return bool(procs)
