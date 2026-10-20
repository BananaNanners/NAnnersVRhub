# Hogwarts Legacy — one-click injector, 0.5.2-dev4

Close the old Hub, extract this preview and install it with your usual Python:

```fish
unzip -n ~/Downloads/NAnnersVRhub-0.5.2-dev4-source.zip -d ~/Downloads
and cd ~/Downloads/NAnnersVRhub-0.5.2-dev4
and python install.py
and ~/.local/bin/nannersvrhub
```

Existing game installs, installed mod/profile files, saves and local test records
are reused. No mod reinstallation is needed if dev3 already passed its file checks.

## Live check

1. Connect the headset through WiVRn. Start Hogwarts from Heroic as before and
   wait until shader loading finishes and the main menu appears.
2. In the Hub, select Hogwarts Legacy and click **Run UEVR injector** once.
   The UEVR window should open without Heroic's EXE file picker.
3. In UEVR, choose **HogwartsLegacy** and **OpenXR**, then **Inject**. The Hub does
   not automate process selection or injection.
4. Close the in-game overlay with **Insert**. Check rendering, tracking, controls,
   stereo depth and menu return in loaded gameplay. Record a new live test with
   a note that the one-click launch was used.
5. Closing the Hub's launch dialog must leave the game and injector running.
   If the injector exits early, the dialog shows its exit code and output tail.

If no injector appears, use the manual guide in the same dialog: **Copy injector
path**, then this game's Heroic **Settings → Wine → Run EXE on prefix**. Do not
launch another injector manually if one is already open.

## Supported launch route

This preview automates native Heroic Wine/Proton runners with an existing prefix.
Proton reuses the recorded build and an installed system or Heroic-bundled umu
launcher when enabled. If umu is disabled/unavailable, direct Proton requires its
existing compatdata/pfx mapping; missing mappings are left untouched. Flatpak
Heroic, missing runners and unsupported layouts use the manual fallback.

Heroic game environment variables are read without shell evaluation. Managed
prefix/runner/ID values override inherited settings from another game. Sync flags
are copied when saved in Heroic. The injector launches in its own folder with
`runinprefix` for Proton; supported umu builds are asked to re-enter the running
game’s container using Heroic’s configured prefix identity; no normal game-launch URI or game-stop routine is used.
Repeated clicks reuse a launcher while it remains alive in this Hub process;
this does not detect an injector opened externally or in an earlier Hub process.

## Evidence

The October 19 16:25:43 PDT SUCCESS is a user-reported test using Heroic's manual
route: rendering, head tracking, controller input and stereo depth passed. The
historical NOT READY snapshot was recorded after disconnecting WiVRn; the later
connected scan at 16:29:25 PDT passed measured runtime checks. Historical records
are preserved. The one-click route and optional voice/body/gesture features still
need their own tests.

Implementation references, inspected October 19, 2026:

- [Heroic runWineCommand](https://github.com/Heroic-Games-Launcher/HeroicGamesLauncher/blob/main/src/backend/launcher.ts)
- [Heroic runner and umu selection](https://github.com/Heroic-Games-Launcher/HeroicGamesLauncher/blob/main/src/backend/utils/compatibility_layers.ts)
- [umu environment and Proton verbs](https://github.com/Open-Wine-Components/umu-launcher/blob/main/docs/umu.1.scd)
