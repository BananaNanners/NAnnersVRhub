# DOOM GOG/Heroic + KHARVOX 1.4 — dev8 test

Dev8 restores DOOM as an experimental ninth profile. Upstream 1.4 adds GOG
executable address profiles and records successful GOG startup/gameplay progress.
Linux/Proton/WiVRn still needs a live test. Existing game histories remain; no
new success record is created by this Hub update.

## Upgrade the Hub

Close the old Hub and run in fish:

```fish
unzip -n ~/Downloads/NAnnersVRhub-0.5.3-dev8-source.zip -d ~/Downloads
and cd ~/Downloads/NAnnersVRhub-0.5.3-dev8
and python install.py
and ~/.local/bin/nannersvrhub
```

This development ZIP does not publish a stable GitHub release or change the
stable update channel. The previous managed Hub remains available for rollback.

## Prepare a fresh KHARVOX extraction

Download **KHARVOX-v1.4.zip**, not Source code, from the
[official 1.4 release](https://github.com/CactusVRStudios/KHARVOX/releases/tag/v1.4.0).
Its SHA-256 is:

```text
83aed75e8b36673a640bf32580bfb3b116884b4db200746e386d4e1d397762f4
```

Verify and extract to a new folder. If `~/Games/KHARVOX-v1.4-test` already exists,
choose another new destination rather than merging files:

```fish
sha256sum ~/Downloads/KHARVOX-v1.4.zip
mkdir -p ~/Games
and mkdir ~/Games/KHARVOX-v1.4-test
and unzip -n ~/Downloads/KHARVOX-v1.4.zip -d ~/Games/KHARVOX-v1.4-test
```

Keep this folder outside the DOOM installation and separate from 1.11. The Hub
does not redistribute, extract, install or remove KHARVOX for you. The selected
extraction stays independently usable through your normal Wine/Proton workflow.

The inspected archive has **112 regular files**, including the shader profiles,
controller assets, OpenXR loader, optional integration binaries and licenses.
The matching launcher file version is **1.4.0.1404**, and the layer DLL is
**1.4.0.1402**. The Hub checks those versions, all required paths and eight
EXE/DLL hashes. Other settings/shader contents are not version-certified.

## First test

1. Launch flat DOOM once through **native Heroic** and close it. Keep Heroic's
   working Proton build and prefix. The new route does not select or download a
   replacement runner. `umu-run` must be available in PATH.
2. Select **DOOM (2016) (GOG/Heroic + KHARVOX, experimental)** in the Hub, then
   **Choose KHARVOX folder…** and select the fresh extraction. This saves only a
   Hub folder selection. Automatic discovery prefers matching PE versions over
   misleading directory names such as old `v1.11` versus new `v1.4`; multiple
   valid copies require an explicit choice. `NANNERS_KHARVOX_DIR` is used when there is no saved folder selection; an
   explicit new GUI choice takes precedence over a stale environment path.
3. Connect WiVRn and run **Preflight**. The game must contain `DOOMx64vk.exe`.
   `DOOMx64.exe` is OpenGL. The supported upstream GOG Vulkan executable digest is
   `a32df8ffa042090f14fe0a200f1c5d7dddf9c947fac223916c252f826f1ecf11`.
   Different or modified game builds stop the experimental VR route for review.
4. Click **Launch DOOM VR**. The Hub starts KHARVOX with native Heroic's saved
   Proton and prefix through umu-run. It does not rewrite Heroic's configuration,
   create a new game prefix, initialize Wine, alter the registry or edit saves.
   The launch window retains a bounded console tail and reports exit status.
5. In KHARVOX, select the complete GOG installation containing `DOOMx64vk.exe`,
   choose **SFS**, and click **Launch Game**. AER is the documented fallback.
   Keep the complete launcher/DLL pair together. KHARVOX manages its own Windows
   manifest path and child-process layer activation when launched.
6. Load a campaign save. Check full stereo rendering, head tracking, movement,
   both controllers, weapon use, menus/return and a short combat sequence. The VR
   intro is separate and does not establish DOOM gameplay success. Keep the game
   window focused; change graphics quality in its main menu rather than during
   a loaded level.
7. Use **Record live test…** for the actual result. If it fails, retain the
   Compatibility report, launch output and Game log diagnostics.

**Launch DOOM (flat)** continues to hand launch back to Heroic. It works without
KHARVOX or a connected headset. Flatpak Heroic, other runners and unsupported
prefix layouts require their own manual Heroic/Wine workflow and live testing.

## Runtime isolation and diagnostics

The launcher process receives OpenXR runtime import (unless explicitly saved
otherwise in Heroic). WiVRn IPC exposure is added when `XDG_RUNTIME_DIR` is
available while preserving other mounts. Those launch settings are not proof
of WineOpenXR or Windows Vulkan-layer interoperability.

The Hub removes inherited foreign Steam prefix/ID/runner variables, reuses the
saved Heroic prefix/Proton, and keeps unrelated saved environment settings as
literal values. GOG receives no Steam AppID override. It removes stale forced
`VK_LAYER_KHARVOX_OPENXR` host activation and paths pointing to this extraction;
it does not load a Windows DLL as a Linux Vulkan layer. The Windows launcher
owns activation in its child process. Other Vulkan layer settings remain.

Game log diagnostics reads up to four files from the resolved Heroic prefix's
Windows user Temp folder: `KHARVOX.log`, `KHARVOX-NATIVE-STEREO.log`,
`KHARVOX-launcher-errors.log` and `KHARVOX-VR-INTRO.log`. Explicit file selection
is available for the build-check or Vulkan-loader logs. Logs remain historical
evidence even while a game is running.

`nativeAttempt=False` refers to the **retired Native renderer** and can occur
normally with SFS/AER. Dev8 reports it as informational. It does not prove VR
success or failure. The earlier prototype's interpretation is not applied to
this new workflow. Actual CVar identity refusals and reported missing layers
remain errors requiring investigation.

The controller tab contains sourced author defaults, including handedness and
gesture options. None are marked user-tested on Linux. Upstream docs:
[1.4 testing scope](https://github.com/CactusVRStudios/KHARVOX/blob/main/Docs/RELEASE_1_4.md),
[GOG Fix 2](https://github.com/CactusVRStudios/KHARVOX/blob/main/Docs/RELEASE_1_4_GOG_FIX2.md).

Elden Ring remains pending an ERVR update for executable 2.7.2.0; dev8 does not
relax its version check. All previous profiles, saved histories and game data
remain separate from this experimental DOOM test.
