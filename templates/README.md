# Button templates

The seeder recognises HLL Vietnam's menus by matching these PNGs against
the screen. They were cut from 2560x1440 Steam screenshots of game build
v1.7 (October 2026) by `tools/crop_templates.py`, which holds the exact
boxes. Frames and templates are both shrunk to 720px high and lightly
blurred before matching, so the same set works from 720p to 1440p and up
(tests/test_matching.py checks 720p, 1080p and 1440p against real
screenshots, and the screens in tests/screens/1080p were captured natively
at 1920x1080). The game draws small text a little differently at each
resolution, so the two text templates also have a 1080p crop,
`server_row.1080p.png` and `create_unit.1080p.png`.

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
| `infantry_create.png` | The + that creates an infantry squad; clicked (the seeder never joins someone else's squad) |
| `create_unit.png` | "Create a Unit" popup that the + opens |
| `create_unit_button.png` | Its CREATE UNIT button; clicked |
| `roles_confirm.png`, `roles_confirm.title.png`, `roles_confirm.select.png` | Edit Roles (own squad) or Select a Role (someone else's squad, in case the game puts us in one), by the F CONFIRM ROLE hint or either title bar; F confirms |
| `admin_yes.png` | Admin message popup; clicked to close it |
| `deploy_button.png` | Deployment screen; F deploys |
| `game_menu_leave.png` | Esc menu open by accident; Esc closes it |

Extra variants of a template go in as `name.<anything>.png`. One named
after a screen height, like `name.1080p.png`, is taken as cut from a
screenshot that tall; any other is taken as cut at 1440p. Players can
override any of these without a new build by dropping a file with the same
name into `%APPDATA%\SynSeeder\templates`.
