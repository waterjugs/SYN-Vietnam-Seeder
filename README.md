# SynSeeder

Seeds the **Syndicate | Competitive Server** on Hell Let Loose: Vietnam.
At a scheduled time it checks the server's population through CRCON. If
the server has fewer than 80 players, it launches the game, joins through
the in-game server browser, picks the team with fewer players, creates
its own infantry squad (it never joins someone else's) and deploys. It
stays in until the server reaches 80, then closes the game.

Tested end to end on a live PC with game build v1.7 (October 2026), at
2560x1440 and 1920x1080.

## Using it

1. Download `SynSeeder.exe` from the
   [latest release](https://github.com/waterjugs/SYN-Vietnam-Seeder/releases/latest)
   and double-click it. Windows may say "Windows protected your PC"
   because the exe isn't code-signed: click **More info**, then
   **Run anyway**.
2. Pick the time to seed each day and Steam or Epic, tick
   **Seed automatically**, and press **Save**. That's it.

It copies itself to `%LOCALAPPDATA%\SynSeeder` and adds a Windows
scheduled task called *SynSeeder*. The PC needs to be on, signed in and
unlocked at that time (it runs late if the PC was asleep). Set the game to
Borderless / Windowed Fullscreen so the seeder can see it. **Seed now** starts a run
straight away and **Stop seeding** ends one and closes the game.

Before the first run, start the game yourself once and finish the tutorial
it opens for a new player (a new Epic copy can do this too, even if you've
played on Steam). The seeder only knows the normal menus.

## What it does

- Skips the whole run if the server is already seeded, unreachable, or if
  the game is already open (it never takes over a game you're playing).
- Finds menu buttons by image matching (see `templates/`), so it doesn't
  depend on fixed screen coordinates or a particular resolution.
- On a fresh join it picks the team with fewer players. When it rejoins
  (the game skips team choice then), it keeps its team unless that team is
  2+ players ahead, in which case it switches once.
- Rejoins after a kick, redeploys after dying, creates a new squad when
  the map changes (if the server still isn't seeded), restarts the game
  after a crash (up to 3 times), and strafes now and then to dodge the
  idle kick.
- Gives up after 4 hours whatever happens.
- Press **Ctrl+Alt+End** to stop a run (or use **Stop seeding** in the
  window). It only sends keys while the game is the active window, so
  alt-tabbing away pauses it rather than typing into your other apps.
  Once the mouse and keyboard have been left alone for 15 seconds it
  brings the game back to the front and carries on; the game's taskbar
  button flashes while it waits for you.
- Works with any keyboard layout (keys are looked up for your layout).

Settings live in `%APPDATA%\SynSeeder\config.json` and the log in
`%APPDATA%\SynSeeder\seeder.log`. If it ever gets stuck on a screen it
doesn't know (after a game patch, say), it saves a screenshot to
`%APPDATA%\SynSeeder\debug`; send that and the log to whoever maintains it.

## Development

```
pip install -r requirements-dev.txt
python -m pytest
python -m seeder --seed      # run a seeding session now (Windows)
python -m seeder --record    # screenshot every 3s, for making templates
python tools/crop_templates.py <dir>   # re-cut templates after a game patch
python tools/make_assets.py  # redraw the window's images and the icon (needs Pillow)
build.bat                    # makes dist\SynSeeder.exe from SynSeeder.spec
```

GitHub Actions runs the tests and builds `SynSeeder.exe` on every push.
Pushing a tag like `v1.0.1` also publishes a release with the exe attached.
