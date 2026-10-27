@echo off
REM Builds dist\SynSeeder.exe. Needs Python 3.12+ on PATH.
python -m venv .venv || exit /b 1
call .venv\Scripts\activate
pip install -r requirements-dev.txt || exit /b 1
pyinstaller --noconfirm SynSeeder.spec || exit /b 1
echo.
echo Built dist\SynSeeder.exe
