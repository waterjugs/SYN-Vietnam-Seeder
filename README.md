# SynSeeder

Seeds the **Syndicate | Competitive Server** on Hell Let Loose: Vietnam.
At a scheduled time it checks the server's population through CRCON. If
the server has fewer than 80 players, it launches the game, joins through
the in-game server browser, picks the team with fewer players and deploys.
It stays in until the server reaches 80, then closes the game.

Status: early development. The seeding logic is written and unit-tested;
the button images and the setup window are still to come.

## What it does

- Skips the whole run if the server is already seeded, unreachable, or if
  the game is already open (it never takes over a game you're playing).
- Finds menu buttons by image matching, so it doesn't depend on fixed screen
  coordinates or a particular resolution.
- Rejoins after a kick, redeploys on a new map, restarts the game after a
  crash (up to 3 times), and strafes now and then to dodge the idle kick.
- Gives up after 4 hours whatever happens.
- Move the mouse into a screen corner to stop it immediately.

Settings live in `%APPDATA%\SynSeeder\config.json` and the log in
`%APPDATA%\SynSeeder\seeder.log`.

## Development

```
pip install -r requirements-dev.txt
python -m pytest
python -m seeder --seed      # run a seeding session now (Windows)
python -m seeder --record    # screenshot every 3s, for making templates
build.bat                    # makes dist\SynSeeder.exe
```
