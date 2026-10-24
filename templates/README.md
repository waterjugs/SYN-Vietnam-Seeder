# Button templates

The seeder finds menu buttons by matching these PNGs against the screen.
Crop them from a **1920x1080** screenshot (they're scaled for other
resolutions). Keep each crop tight around the button's text or icon, with
as little background as possible. Extra variants go in as
`name.<anything>.png`, for example `server_row.hover.png`.

Players can override any of these by dropping a file with the same name in
`%APPDATA%\SynSeeder\templates`.

| File | What to crop | Status |
| --- | --- | --- |
| `menu_play.png` | Main menu button that opens the server browser | needed |
| `browser_search.png` | Server browser search box | needed |
| `server_row.png` | The Syndicate server's name in the browser list | needed |
| `browser_join.png` | Server browser Join button | needed |
| `team_us.png` | US faction button on team select | needed |
| `team_nva.png` | NVA faction button on team select | needed |
| `role_rifleman.png` | Rifleman role card | needed |
| `spawn_hq.png` | An HQ spawn point on the deploy map | needed |
| `deploy_button.png` | Deploy button | needed |
| `popup_ok.png`, `popup_continue.png`, `popup_close.png` | Buttons on dialogs that can block the menus (news, errors) | optional |

The menu order above is a guess from the original HLL. It gets confirmed
against real HLL Vietnam screenshots (`SynSeeder.exe --record`).
