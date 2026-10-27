# PyInstaller recipe for SynSeeder.exe:  pyinstaller --noconfirm SynSeeder.spec
# Same as the old one-line command, plus the window's images, the app icon and
# the name and version Windows shows in Properties and Task Manager.

import re
import sys
from pathlib import Path

root = Path(SPECPATH)
version = re.search(r'__version__ = "(\d+)\.(\d+)\.(\d+)"', (root / "seeder" / "__init__.py").read_text()).groups()

version_info = None
if sys.platform == "win32":  # the version resource only exists on Windows
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo)

    numbers = tuple(int(n) for n in version) + (0,)
    text = ".".join(version)
    version_info = VSVersionInfo(
        ffi=FixedFileInfo(filevers=numbers, prodvers=numbers),
        kids=[
            StringFileInfo([StringTable("040904B0", [
                StringStruct("FileDescription", "SYN Vietnam Seeder"),
                StringStruct("FileVersion", text),
                StringStruct("InternalName", "SynSeeder"),
                StringStruct("OriginalFilename", "SynSeeder.exe"),
                StringStruct("ProductName", "SYN Vietnam Seeder"),
                StringStruct("ProductVersion", text),
            ])]),
            VarFileInfo([VarStruct("Translation", [0x0409, 0x04B0])]),
        ],
    )

a = Analysis(
    [str(root / "run_seeder.py")],
    datas=[(str(root / "templates"), "templates"), (str(root / "assets"), "assets")],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SynSeeder",
    console=False,
    icon=str(root / "assets" / "synseeder.ico"),
    version=version_info,
)
