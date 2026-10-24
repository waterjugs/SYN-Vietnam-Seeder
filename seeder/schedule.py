"""The daily Windows scheduled task, and keeping one stable copy of the exe.

The task is registered from XML rather than plain schtasks flags so it can
also run on battery, start late if the PC was off or asleep at the time,
and never start twice.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

TASK_NAME = "SynSeeder"
CREATE_NO_WINDOW = 0x08000000


def install_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share"
    return Path(base) / "SynSeeder"


def seed_command() -> tuple[str, str]:
    """(program, arguments) that start a seeding run.

    A built exe copies itself to %LOCALAPPDATA%\\SynSeeder first, so the task
    keeps working if the download is moved or deleted.
    """
    if getattr(sys, "frozen", False):
        target = install_dir() / "SynSeeder.exe"
        current = Path(sys.executable).resolve()
        if current != target.resolve():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(current, target)
        return str(target), "--seed"
    return sys.executable, "-m seeder --seed"


def task_xml(start_time: str, program: str, arguments: str, now: datetime | None = None) -> str:
    hour, minute = (int(part) for part in start_time.split(":"))
    now = now or datetime.now()
    start = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if start <= now:
        start += timedelta(days=1)
    user = escape(f"{os.environ.get('USERDOMAIN', '')}\\{os.environ.get('USERNAME', '')}".strip("\\"))
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Seeds the Syndicate HLL Vietnam server. Change it from SynSeeder.exe.</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>{start.strftime("%Y-%m-%dT%H:%M:%S")}</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{user}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <Enabled>true</Enabled>
    <ExecutionTimeLimit>PT6H</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{escape(program)}</Command>
      <Arguments>{escape(arguments)}</Arguments>
    </Exec>
  </Actions>
</Task>
"""


def _schtasks(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["schtasks", *args],
        capture_output=True,
        text=True,
        creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


def schedule(start_time: str) -> None:
    """Creates or replaces the daily task. Raises RuntimeError on failure."""
    program, arguments = seed_command()
    xml = task_xml(start_time, program, arguments)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "task.xml"
        path.write_text(xml, encoding="utf-16")
        result = _schtasks("/Create", "/TN", TASK_NAME, "/XML", str(path), "/F")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "schtasks failed")


def unschedule() -> None:
    if is_scheduled():
        result = _schtasks("/Delete", "/TN", TASK_NAME, "/F")
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "schtasks failed")


def is_scheduled() -> bool:
    return _schtasks("/Query", "/TN", TASK_NAME).returncode == 0
