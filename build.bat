@echo off
REM Builds dist\SynSeeder.exe. Needs Python 3.12+ on PATH.
python -m venv .venv || exit /b 1
call .venv\Scripts\activate
pip install -r requirements-dev.txt || exit /b 1
pyinstaller --onefile --noconsole --name SynSeeder --add-data "templates;templates" run_seeder.py || exit /b 1
echo.
echo Built dist\SynSeeder.exe
