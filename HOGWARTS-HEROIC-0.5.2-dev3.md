# Hogwarts Legacy — Heroic/Epic, 0.5.2-dev3

This corrects dev2's Steam-only assumption. The user confirmed the game is an
Epic Games copy installed through Heroic. Gameplay starts **UNVERIFIED**; the
correction does not add a successful live test or change any saved results.

## Install this corrected Hub

Close the Hub, then run in fish:

```fish
unzip -n ~/Downloads/NAnnersVRhub-0.5.2-dev3-source.zip -d ~/Downloads
and cd ~/Downloads/NAnnersVRhub-0.5.2-dev3
and python install.py
and ~/.local/bin/nannersvrhub
```

Confirm five games and existing histories are present. Select **Hogwarts Legacy
(Heroic/Epic + UEVR)**. Its guide/compatibility report should show the Heroic
configuration, Epic identity, configured runner and prefix. The Hub reads only
the Epic install record and that game's settings; it does not read account
credentials or change Heroic settings. Steam launch-option copying is disabled
for this recipe. The other four games retain their Steam workflows.

## Install the same two mod ZIPs

Use **UEVR.zip** and **HogwartsLegacy.zip** from the
[author's v2.0.6 release](https://github.com/jbusfield/HL_UEVR/releases/tag/v2.0.6).
Already downloaded files can be reused. They are not included in this Hub ZIP.

1. Launch Hogwarts once through Heroic using its existing runner. Check its Wine
   prefix and selected Wine/Proton version in Heroic. Close the game for file
   installation.
2. In the Hub, **Install mod file…** selects UEVR.zip. Files go into
   `<actual-prefix>/drive_c/uevr/`.
3. **Install profile…** selects HogwartsLegacy.zip. Its full contents go into the
   existing Windows user's `AppData/Roaming/UnrealVRMod/HogwartsLegacy/` inside that
   prefix. This includes scripts, data, native plugins and models. Existing
   untracked VR profile contents are backed up before replacement. A recorded
   Hub profile must be removed through the Hub before installing another.
4. In Heroic's game environment settings, review the variable name
   `PRESSURE_VESSEL_IMPORT_OPENXR_1_RUNTIMES` with value `1` when using Proton.
   The Hub does not change or certify that setting. Follow the guide's Frame
   Generation/HDR checks.
5. If the injector requests .NET, run the Windows x64 .NET 6 Desktop Runtime
   installer with this game's **Run EXE on prefix** in Heroic. Linux dotnet and
   Steam AppID 990080 do not identify this Epic copy's prefix.

## Play and inject

1. Connect through WiVRn and launch the game in Heroic. **Launch in Heroic** in
   the Hub requests that Epic game from its matching native/Flatpak client.
2. Wait for shader loading to finish and the main menu to appear. Choose
   **UEVR via Heroic…** in the Hub. Copy the displayed injector path; opening its
   folder or Heroic is optional.
3. In Heroic, open Hogwarts **Settings -> Wine -> Run EXE on prefix** and select
   that UEVRInjector.exe. Heroic owns the runner, prefix and launch environment;
   the Hub does not launch this injector through Steam protontricks.
4. In UEVR, select the HogwartsLegacy process and **OpenXR**, then inject. Load
   a save. Close the in-game UEVR overlay with **Insert** before checking VR;
   review 2D Screen Mode if only a floating screen is visible.
5. Test rendering, stereo depth, head tracking, movement/turning, wand aiming and
   casting, then game-menu entry/exit. Optional gesture/body/voice features need
   separate tests. Record explicit results with **Record live test…**.

Compatibility can remain **REVIEW REQUIRED** with every file present: settings,
injection and actual gameplay need manual review. **Log diagnostics…** follows the
selected user's HogwartsLegacy/log.txt. Missing logs can be selected explicitly.
Support reports use the same resolved prefix, not a guessed Steam location.

## Discovery and troubleshooting

Native metadata normally lives under `$XDG_CONFIG_HOME/heroic/` or
`~/.config/heroic/`; Flatpak metadata under
`~/.var/app/com.heroicgameslauncher.hgl/config/heroic/`. The Hub matches Hogwarts
in `legendaryConfig/legendary/installed.json` and reads the matching
`GamesConfig/<Epic app name>.json`. It uses that record's game path, winePrefix
and wineVersion. Epic identities are discovered rather than hardcoded.

Both `<configured-prefix>/drive_c` and `<configured-prefix>/pfx/drive_c` layouts
are supported. Aliases resolving to the same prefix count once; different
prefixes at both locations stop installation for review. Existing AppData
users are inspected: Proton prefers its existing steamuser; Wine uses a single
unambiguous existing user. Ambiguous users and paths resolving outside the prefix
are rejected. No prefix or Windows user is guessed or created by discovery.

If two Heroic installations contain Hogwarts, explicitly select the intended
config folder for Hub discovery, for example:

```fish
env NANNERS_HEROIC_CONFIG="$HOME/.config/heroic" ~/.local/bin/nannersvrhub
```

A non-default portable config can be selected for discovery/installation, but
open that intended Heroic client manually for launching. The override does not
change Heroic's own launch configuration. Missing native/Flatpak commands also
leave manual Heroic launch available.

No Steam-to-Heroic inventory migration is automatic. If an earlier Hub record
points at another prefix, compatibility marks it as outside the current install.
Review it before removal/reinstallation; game saves are separate from the VR
profile and are not moved by this workflow.

## Validation

**293 tests passed with PySide6**, including native/Flatpak discovery, direct and
nested prefixes, existing Wine users, ambiguous/corrupt metadata, out-of-prefix
paths, game launch routing and the guided injector controls. The original Steam
workflows and Hub updater tests also passed.

In an isolated Heroic fixture, the real official archives installed all **10
injector files** and **192 profile files**, matching every archive byte. No Steam
lookup occurred. Heroic metadata, an existing game save and unrelated Hub records
were preserved; removing the VR profile restored its previous backup. The game
and Windows injector were not executed, so this is not gameplay evidence.

Primary references: [Heroic Wine/Proton and Run EXE on prefix](https://github.com/Heroic-Games-Launcher/HeroicGamesLauncher/wiki/How-To:-Wine-and-Proton),
[Heroic Epic metadata paths](https://github.com/Heroic-Games-Launcher/HeroicGamesLauncher/blob/main/src/backend/storeManagers/legendary/constants.ts),
[Heroic launch protocol](https://github.com/Heroic-Games-Launcher/HeroicGamesLauncher/blob/main/src/backend/protocol.ts),
[HL_UEVR v2.0.6](https://github.com/jbusfield/HL_UEVR/releases/tag/v2.0.6).
