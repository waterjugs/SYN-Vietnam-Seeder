# SynSeeder Terms of Service

Last updated: 30 October 2026

SynSeeder is a free, unofficial tool that plays Hell Let Loose: Vietnam for you so a community server fills up. By running it, you agree to these terms. The short version:

- It's provided as is, with no promise that it works or keeps working after a game update.
- While it runs, it controls your mouse and keyboard in the game and opens and closes the game by itself.
- Before each run it checks GitHub for a newer version and installs it, unless you turn this off. An update can change what the app does.
- Steam's rules ban automated play like this, and Epic's and the game's rules may too. If your account is warned, suspended or banned, that risk is yours.
- Don't use it to cheat, get around anti-cheat, or run accounts the rules don't allow.

The full terms below are what count; this summary is only a guide to them.

## 1. Who we are and agreeing to these terms

These terms are an agreement between you and the GitHub user waterjugs ("we", "us"), who makes SynSeeder ("the app"). By running SynSeeder, you agree to these terms. The [SynSeeder Privacy Policy](PRIVACY.md) explains what the app stores and sends. If you don't agree to these terms, don't use SynSeeder.

You must be 18 or older, and old enough to make a binding agreement where you live. Only run SynSeeder on a PC, and with a game account, that you own or are allowed to use for this.

## 2. What SynSeeder does on your PC

During a run, SynSeeder takes over the game the way a player would, and you agree to let it. It:

- checks GitHub for a newer version of SynSeeder and, if there is one, downloads it, installs it and lets the new version carry on with the run (see section 8);
- checks the server's player count and goes ahead only if the server has fewer than 80 players, the game isn't already open and the PC isn't locked;
- starts the game through Steam or Epic, joins the Syndicate | Competitive Server through the in-game server browser, picks a team, creates its own squad and deploys;
- moves the mouse, clicks and presses keys in the game, including a small movement about once a minute so the game doesn't kick it for being idle, and rejoins, redeploys or restarts the game when it needs to;
- clicks "Yes" on admin messages so the run can carry on, so you may not see a message an admin sends you;
- once your mouse and keyboard have been left alone for 15 seconds, brings the game to the front, which can mean an Alt key tap, or a mouse signal that doesn't move the pointer, in whatever window you're using (watching a video or using a gamepad counts as leaving them alone);
- closes the game when the server reaches 80 players, after 4 hours, when it can't get in, or when you press **Stop seeding** or Ctrl+Alt+End, even if you've started playing in it yourself;
- copies itself to `%LOCALAPPDATA%\SynSeeder` when you press **Seed now**, or **Save** with **Seed automatically** ticked. **Seed now** saves your settings too, so with that box ticked either button adds a Windows scheduled task that starts a run every day at your chosen time, and with it unticked either button removes the task. If the PC was off or asleep at that time, the run starts when the PC is next available, which can be hours late. It runs on battery too, and keeps going if a laptop is unplugged.

It's designed to send keys and clicks only while the game is the active window, but we can't promise that input never lands somewhere else. Save your work before a run is due. You're responsible for your PC, the power it uses and anything else running on it.

## 3. Your licence to use it

We give you a free, personal, non-exclusive, non-transferable licence to download and run SynSeeder on PCs you own or control, under these terms. We can end it if you break them.

SynSeeder's source code is public on GitHub so anyone can see what it does. It has no open-source licence, so we keep all rights in it. GitHub's own terms let anyone view the code and fork it on GitHub. Beyond that, don't sell SynSeeder, pass it off as your own, or share changed copies of the app. If we add an open-source licence later, that licence decides what you can do with the code. To share SynSeeder, link to the official [GitHub releases](https://github.com/waterjugs/SYN-Vietnam-Seeder/releases) rather than passing the exe around, so people get the current, unchanged version.

SynSeeder includes third-party software that stays under its own licence, including Python, Tcl/Tk, OpenCV, FFmpeg, NumPy, OpenBLAS, psutil, mss, the PyInstaller bootloader and the Inter font. Nothing in these terms limits your rights under those licences.

## 4. Game, Steam and Epic rules, and the risk to your account

Steam's rules ban automated play like SynSeeder's, and the game's and Epic's rules may too. You use it at your own risk. As of 29 October 2026:

- **Steam.** Section 4.C of the [Steam Subscriber Agreement](https://store.steampowered.com/subscriber_agreement/) (updated 10 September 2026) says you may not use "scripts, bots, macros, or other non-human-controlled systems" to interact with games on Steam. Its examples include faking playtime and "earning rewards or progress without genuine user input". Under section 4.D, Valve may restrict or terminate your whole Steam account or just the game, and doesn't have to warn you before terminating. Valve looks for automation itself, and game hosts may report it to Valve.
- **Epic.** Section 4 of the [Epic Games Terms of Service](https://legal.epicgames.com/epicgames/tos) covers Epic's launcher and your Epic account. It says you agree not to "use bot software or services to automate your use" of them. Its examples of cheats include bots and scripts, and Epic may suspend or terminate your account for cheats without notice. If you got the game on the Epic Games Store, the [Epic Games Store EULA](https://legal.epicgames.com/store/eula?lang=en-US) also applies: section 2 bans using "unauthorized software programs to gain advantage" in a game, and under section 9 your licence ends automatically if you break it.
- **The game.** Section 2.1 of the [Hell Let Loose: Vietnam EULA](https://store.steampowered.com/eula/3079210_eula_0) from Team17 restricts combining third-party software with the game, and section 9.1 lets Team17 end your licence and game account if you break it.
- **Anti-cheat.** The game runs Easy Anti-Cheat, Epic's kernel-level anti-cheat. Epic says it also uses gameplay analysis and player reports to spot cheats. SynSeeder doesn't read or change the game's memory and doesn't try to hide from anti-cheat. That doesn't make it allowed: automated play breaks the rules above whether or not anyone notices. Epic's terms also say that just having cheats, which they say include bots, on your PC can get your Epic account suspended.

The result can be losing your Steam or Epic account and everything bought on it, with no refund. We can't change these rules or get a ban lifted, and we aren't responsible for any action taken against your accounts. These platforms change their terms, so check the current versions yourself. If you aren't comfortable with the risk, don't use SynSeeder.

## 5. What you must not do with it

Don't use SynSeeder, or a changed version of it, to:

- cheat, or gain an unfair advantage in a match;
- get around, hide from or interfere with anti-cheat or any other protection in the game, Steam or Epic, including by hiding a virtual machine from it;
- play on accounts you don't own, or on more accounts than the game's and platform's rules allow;
- break the rules of the server you're seeding, or disrupt or harass other players;
- flood the player-count service it reads, or any other service, with requests;
- do anything illegal.

Server admins can kick or ban the seeder like any other player. If a server's admins ask you to stop seeding their server, stop. SynSeeder clicks "Yes" on admin messages during a run, so you may not see a request sent in the game. Check the server's Discord or website now and then, and stop if the seeder keeps getting kicked.

## 6. Not affiliated with the game's makers, Valve, Epic or the server

SynSeeder is an independent, unofficial tool. It isn't made, endorsed, sponsored or supported by Expression Games or Team17 (the developer and publisher of Hell Let Loose: Vietnam), Valve (Steam), Epic Games (the Epic Games Store and Easy Anti-Cheat), or the makers of CRCON, the admin tool behind the server's stats page. It also isn't an official tool of the Syndicate | Competitive Server, and the server's owners aren't responsible for it.

Hell Let Loose, Steam, Epic Games and the other names here are trademarks of their owners, used only to say what SynSeeder works with. The small pictures of the game's buttons inside SynSeeder belong to the game's makers and are included only so the app can recognise those buttons.

## 7. No warranty, and limits on liability

SynSeeder is free and provided "as is" and "as available", without warranties of any kind, express or implied, including that it's fit for a purpose, works without errors, or keeps working after a game update. A game patch can break it at any time.

As far as the law allows, we aren't liable for any loss or damage that comes from using SynSeeder or not being able to use it. That includes action taken against your game, Steam or Epic account; lost progress, data or work; problems with your PC; and anything the game, the server or its admins do.

If you break these terms and someone makes a claim against us because of it, you're responsible for that claim and its reasonable costs, as far as the law allows.

Some places don't allow these exclusions or limits. There, they apply only as far as the law allows, and nothing in these terms takes away rights you have by law as a consumer.

## 8. Changes, stopping, privacy and contact

**Updates.** Updates are on unless you turn them off. Before each run, SynSeeder checks its GitHub releases for a newer version. If there is one, it downloads it, installs it and carries on the run with the new version, without asking you first. An update can change anything the app does, including what section 2 describes. SynSeeder checks that each download arrived whole and matches what GitHub lists for it, but it can't tell whether a release itself is safe, and the app isn't code-signed. If you'd rather check each version yourself, turn updates off (the Privacy Policy says how); you then won't get fixes after a game patch.

**Changes to SynSeeder and these terms.** We may change SynSeeder, or stop offering it, at any time. We may also change these terms. When we do, we'll change the date at the top and say so in the release notes. The new terms apply 14 days after that date, so you have time to stop if you don't agree. Updates install themselves, so you won't see the release notes unless you look; check the SynSeeder GitHub page now and then. Using SynSeeder after the new terms apply means you accept them.

**Stopping.** You can stop using SynSeeder at any time: untick **Seed automatically**, press **Save**, then delete the app and its folders (the Privacy Policy lists them). We can end your permission to use it if you break these terms. Sections 5, 6 and 7 still apply after that.

**Privacy.** The [SynSeeder Privacy Policy](PRIVACY.md) explains what the app stores and sends. In short, what the app saves stays on your PC. On its own, it only asks the server's stats page for the player count, and checks GitHub for updates and downloads them. Playing on the server shares your player name and ID with the server and its admins, just as when you play yourself.

**The rest.** If a court finds part of these terms unenforceable, the rest still applies. If we don't enforce a term straight away, we can still enforce it later. These terms are the whole agreement between you and us about SynSeeder. They're governed by the laws of the United States of America, leaving aside any rule that would apply another place's law. If you live somewhere whose laws give you rights that an agreement can't take away, you keep those rights.

**Contact.** Open an issue at [github.com/waterjugs/SYN-Vietnam-Seeder/issues](https://github.com/waterjugs/SYN-Vietnam-Seeder/issues). For anything private, such as sending us your log or screenshots, message us on [Discord](https://discord.com/users/132721731096936448) instead (Discord user ID 132721731096936448).
