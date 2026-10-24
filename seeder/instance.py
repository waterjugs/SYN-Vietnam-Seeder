"""Making sure only one seeding run happens at a time, and stopping it."""

from __future__ import annotations

import logging
import os

import psutil

log = logging.getLogger(__name__)

MUTEX_NAME = "Local\\SynSeederSeeding"
ERROR_ALREADY_EXISTS = 183
_held = None


def claim() -> bool:
    """True if this process may seed; False if another run already is.

    Holds a named mutex for the life of the process. Always True off Windows.
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
