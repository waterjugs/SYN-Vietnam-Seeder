# Button templates

The seeder recognises HLL Vietnam's menus by matching these PNGs against
the screen. They were cut from 2560x1440 Steam screenshots of game build
v1.7 (October 2026) by `tools/crop_templates.py`, which holds the exact
boxes. Frames and templates are both shrunk to 720px high and lightly
blurred before matching, so the same set works from 720p to 1440p and up
(tests/test_matching.py checks 720p, 1080p and 1440p against real
screenshots).

| File | Screen it identifies / what gets clicked |
| --- | --- |
| `menu_enlist.png` | Main menu; clicked to open the server browser |
| `browser_search.png` | Empty server search box; clicked, then the server name is typed |
| `server_row.png` | The Syndicate server's name in the list |
| `browser_join.png` | JOIN buttons; the one on the server's row is clicked |
| `browser_refresh.png` | Server browser with our server missing; R refreshes every 20 s |
| `select_force.png` | Select Force screen (fresh join); the smaller team's card is clicked |
| `force_us.png` / `force_nva.png` | The US and NVA cards on Select Force |
| `switch_team.png` | Units screen (the game has already picked a team) |
| `faction_nva.png` | NVA badge on Units/Deployment, to tell which team we're on |
| `squad_join.png` | Join arrow on an infantry squad |
| `infantry_create.png` | The + that creates an infantry squad |
| `roles_confirm.png` | Edit Roles screen; F confirms |
| `admin_yes.png` | Admin message popup; clicked to close it |
| `deploy_button.png` | Deployment screen; F deploys |
| `game_menu_leave.png` | Esc menu open by accident; Esc closes it |

Extra variants of a template go in as `name.<anything>.png`. Players can
override any of these without a new build by dropping a file with the same
name into `%APPDATA%\SynSeeder\templates`.
