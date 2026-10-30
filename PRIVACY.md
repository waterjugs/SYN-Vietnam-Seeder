# SynSeeder Privacy Policy

Last updated: 30 October 2026

SynSeeder sends nothing about you to us, and it doesn't sell your information. It has no accounts, ads, analytics or crash reporting, and it never uploads your files. Like anything that goes online, it shows your IP address to the sites it talks to: the server's stats page, for the player count, and GitHub, to check for and download updates. Everything it saves (settings, a log and the occasional screenshot) stays in folders on your own PC until you delete it.

This policy covers the SynSeeder app (SynSeeder.exe), made by the GitHub user waterjugs ("we", "us"). It doesn't cover Hell Let Loose: Vietnam, Steam, Epic, GitHub, Cloudflare, Discord, or the game server and its stats page. Other people run those, under their own rules and their own privacy policies where they have them.

## What SynSeeder keeps on your PC

SynSeeder saves only the items below, all on your PC, and none of them is sent anywhere.

| What | Where | What's in it | Kept until |
| --- | --- | --- | --- |
| Settings | `%APPDATA%\SynSeeder\config.json` | Your daily start time, Steam or Epic, and the seeding settings (server name, stats address, timings, updates on or off). Nothing about you. | You delete it |
| Log | `%APPDATA%\SynSeeder\seeder.log` | Times, player counts, each step of a run and any errors, which together show when your PC was on and in use. It can include your Windows user name (inside folder paths) and the name of a program that was in front of the game. | You delete it. It isn't trimmed automatically |
| Stuck screenshots | `%APPDATA%\SynSeeder\debug\` | A full-colour picture of the area where the game is drawn (or of your whole main screen, if it can't find the game window), saved when a run seems stuck while joining. It shows whatever is there, which can include player names, chat and any window or notification on top of the game. | The newest 20 are kept. Each time a new one is saved, older ones are deleted, so don't keep your own pictures in that folder |
| Recorded screenshots | `%APPDATA%\SynSeeder\screenshots\` | Only if you start the app with `--record`, a developer option for making button images: your whole main screen every 3 seconds, for 10 minutes by default (about 200 pictures). | You delete them |
| A copy of the app | `%LOCALAPPDATA%\SynSeeder\SynSeeder.exe` | Made when you press Seed now, or Save with Seed automatically ticked, so the schedule keeps working if you move or delete your download. Newer versions from GitHub replace it. | You delete it |
| An update being installed | `%LOCALAPPDATA%\SynSeeder\SynSeeder-update.exe` | A newer version downloaded from GitHub. It copies itself over the app above and finishes that run. If something still has the app open, such as a SynSeeder window started from it, the download stays here so a later run can finish installing it without downloading it again. While it downloads and copies itself into place, SynSeeder-update.exe.part and SynSeeder.exe.new can also appear here for a short time. | The first run after the update is in place deletes it |
| Note of a failed update | `%APPDATA%\SynSeeder\update-failed.json` | Only if a new version fails to start: its version number and how many times it failed. After three failures SynSeeder skips that version and waits for the next one. | You delete it |
| Scheduled task named SynSeeder | Windows Task Scheduler | Starts a run at your chosen time each day, under your Windows account and without admin rights. Windows stores your account name with the task. | You untick Seed automatically and press Save or Seed now |
| Temporary files | A `_MEI` folder in `%TEMP%` | The app's own parts, unpacked each time it starts. | It closes (one can be left behind if a run is stopped or crashes) |

On a work or school PC with a roaming profile, Windows may copy the `%APPDATA%` folder to your organisation's servers.

## What it looks at while it runs

To play the game, SynSeeder reads a few things on your PC as it goes. It uses them on the spot and doesn't save or send them, apart from the log lines and stuck screenshots listed above.

- **The game's picture.** Every couple of seconds while joining, and about every 30 seconds once in, it captures the area where the game is drawn (or your whole main screen, if it can't find the game window) and compares it with pictures of the game's buttons. It keeps only a grey, shrunk copy of each capture in memory, until the next capture replaces it.
- **Running programs.** It reads the names of running programs to find the game, and the command lines of running programs to find other SynSeeder runs (so it never runs twice and Stop seeding works). When another window keeps the game from coming to the front, it notes that program's name in the log.
- **How long since you last used the mouse or keyboard.** Windows reports only the time of the last input, never what you typed or clicked. SynSeeder uses it to wait until you've left the PC alone for 15 seconds before bringing the game to the front.
- **The Ctrl+Alt+End shortcut.** It registers this one shortcut to stop a run. Windows tells it only when that exact shortcut is pressed; it doesn't see any other keys.
- **Your keyboard layout,** so it presses the right keys on any layout.
- **Whether the PC is locked,** because it can't play on a locked screen.
- **Epic's list of installed games,** only if you choose Epic, to find Hell Let Loose: Vietnam's entry so it can start it.

Apart from what's listed here, SynSeeder doesn't open your files, browser, messages, contacts or accounts, and it doesn't record your keystrokes. A screen capture can still catch a message or notification that pops up over the game.

## What goes over the internet

SynSeeder itself makes only the requests below. None of them includes anything about you beyond your IP address, the time, and that you use SynSeeder (GitHub also sees which version you have).

| Request | When | Goes to | What the receiver sees |
| --- | --- | --- | --- |
| The server's player count | When the window opens, at the start of each run, then about every 30 seconds while seeding | The server's public stats page, `syn-stats-nam.radicalgamingstats.com`, through Cloudflare | Your IP address, the time, and that the request came from "SynSeeder" |
| Is there a newer version? | At the start of each run | GitHub (`api.github.com`) | Your IP address, the time, and which SynSeeder version you have |
| Downloading the newer version | Only when there is one | GitHub | Your IP address, the time, which SynSeeder version you have and which one you're getting |

The answers hold only public information: the server's map, score and player counts, and GitHub's release details. We don't run the stats page. We couldn't find a privacy policy for it, so we can't tell you whether its owners keep a record of these requests. Requests to it pass through Cloudflare, which handles them for whoever runs the stats page ([Cloudflare's privacy policy](https://www.cloudflare.com/privacypolicy/)). GitHub handles its requests under the [GitHub General Privacy Statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement).

The **Terms of Service** and **Privacy Policy** links at the bottom of SynSeeder's window open these documents on GitHub in your web browser. That happens only when you click one.

**Turning updates off.** Press **Save** once in SynSeeder so the settings file exists, then close SynSeeder. Paste `%APPDATA%\SynSeeder` into File Explorer's address bar and open `config.json` in Notepad. Change `"auto_update": true` to `"auto_update": false` and save the file. Type false in small letters with no quote marks around it, and leave everything else as it is. If the file has a mistake in it, SynSeeder ignores the whole file and updates come back on.

## The game, Steam or Epic, and the server

When SynSeeder starts the game, everything that normally happens when you play happens as usual. Other people run each of these, under their own rules:

- Steam or Epic signs you in, records play time and may show friends that you're playing ([Steam Privacy Policy](https://store.steampowered.com/privacy_agreement/), [Epic Games Privacy Policy](https://legal.epicgames.com/epicgames/privacy-policy)).
- The game and its anti-cheat, Easy Anti-Cheat, collect what they normally do. The game's website points to Team17's [Privacy and Cookie Notice](https://www.team17.com/privacy-policy/), but that notice covers Team17's website and doesn't say what the game collects. Easy Anti-Cheat is run by Epic Games.
- The server's admins see you like any other player. Their admin tool, CRCON, can record your player name and past names, your platform ID (such as your Steam ID), when you joined and left, your kills and your chat. If it's set up to, it can also look up your Steam profile, such as your country and any bans. It can show some of this on public stats pages.

SynSeeder doesn't control any of this, and none of it passes through us. It also clicks "Yes" on admin messages so the run can carry on, so you may not see a message an admin sends you during a run.

## Sending your log or screenshots to someone

Your log and screenshots leave your PC only if you send them, for example when asking for help after a game update breaks something. Check them first: the log can show your Windows user name, and screenshots can show your in-game name, other players' names and chat. Crop or blank out anything you'd rather not share, especially before posting in a public GitHub issue.

If you send them to us privately, on [Discord](https://discord.com/users/132721731096936448) (user ID 132721731096936448), we use them only to work out what went wrong. We don't share them with anyone else, and we delete our copies once the problem is fixed. Discord handles those messages under its own [privacy policy](https://discord.com/privacy). Anything you post in a public GitHub issue or a chat can be seen and saved by anyone, and we can't take it back.

## Removing everything SynSeeder put on your PC

Five steps remove all of it. If you've already deleted the app, do this instead of step 1: open Task Scheduler from the Start menu and delete the task named SynSeeder.

1. Open SynSeeder, press **Stop seeding** if a run is going, untick **Seed automatically** and press **Save**. This deletes the scheduled task.
2. Close SynSeeder.
3. Delete the folders `%APPDATA%\SynSeeder` and `%LOCALAPPDATA%\SynSeeder` (paste each path into File Explorer's address bar to find it).
4. Delete the SynSeeder.exe you downloaded.
5. If a run was ever stopped or crashed, paste `%TEMP%` into File Explorer's address bar and delete any folders whose names start with `_MEI`. Other apps make these folders too, so skip any that Windows says are in use.

Unless you've sent us files, we never receive any of this, so there's nothing to delete on our side.

## Your rights, children, changes and contact

**Your rights.** Privacy laws such as the GDPR and the CCPA give you rights over personal data that a developer holds about you. We don't hold any, unless you've sent us your log or screenshots. If you have, message us privately on [Discord](https://discord.com/users/132721731096936448) and we'll tell you what we still have and delete it. Everything else listed above is on your PC and under your control.

**Children.** SynSeeder collects nothing from anyone, children included. Use it only if you're 18 or older.

**Changes.** If a new version will collect, keep or send anything new, we'll update this policy at least 14 days before we release it. We'll change the date at the top and say so in the release notes. Updates install themselves, so check this page now and then, or turn updates off if you'd rather decide for yourself.

**Contact.** Questions about this policy: open an issue at [github.com/waterjugs/SYN-Vietnam-Seeder/issues](https://github.com/waterjugs/SYN-Vietnam-Seeder/issues). For anything about your own files, message us privately on [Discord](https://discord.com/users/132721731096936448) instead. Issues are public, so don't paste your log or screenshots there without checking them first.

Using SynSeeder is also covered by the [SynSeeder Terms of Service](TERMS.md).
