# Elden Ring — ERVR 0.4.0 preview

This eighth profile is experimental. The archive was inspected and its installer
tested without executing the mod. No Linux/WiVRn gameplay result is bundled.
The previous seven recipes, their controller guides and local histories remain.

## Upgrade the Hub

Close the old Hub, then run in fish:

```fish
unzip -n ~/Downloads/NAnnersVRhub-0.5.3-dev7-source.zip -d ~/Downloads
and cd ~/Downloads/NAnnersVRhub-0.5.3-dev7
and python install.py
and ~/.local/bin/nannersvrhub
```

Use the extracted preview installer; this ZIP does not publish a stable release
or change the in-app update channel. The managed installer retains the previous
Hub version for rollback. It does not install game mods during a Hub upgrade.

## Reinstall after removal

Dev7 accepts an empty `Game/ERVR` directory or one containing only the regular
`ERVR.log` file left by removal, preserving the log. After installing this Hub
update, use **Install mod file…** with the same ERVR ZIP again. Other files,
settings, DLLs, symlinks and unknown directories still require review.

## Install and launch

1. Start Elden Ring flat through Steam with your chosen Proton once. Confirm the
   Hub finds `Game/eldenring.exe` and the game's own prefix. ERVR documents PE file
   versions **2.6.2.0** (game 1.16.2) and **2.7.1.0** (game 1.17.1). The Hub reads
   this metadata without running the EXE and stops unknown builds before launch.
2. Back up saves using your usual workflow. Set the game's startup network option
   to **Play Offline**, quit, and put **Steam offline**. The mod requires an
   EAC-disabled offline route and does not support multiplayer. Those settings
   remain manual prerequisites; the Hub does not certify network isolation.
3. In Games, select Elden Ring and install the single **ERVR V0.4.0 ZIP** from the
   [author's Files page](https://www.nexusmods.com/eldenring/mods/10711?tab=files).
   The uploaded, renamed download is accepted by content hash. Do not extract it
   into the Hub source folder. The installer normalizes its Windows separators
   and installs all ten files under `Game/` with original-file backups.
4. Existing `dxgi.dll`, `dinput8.dll`, `ReShade.ini`, an untracked ERVR directory,
   or recognized R.E.A.L. VR files block installation. Review/remove the previous
   mod with its original installer before proceeding. This profile does not
   combine other loaders or attempt to certify every possible mod conflict.
5. **Copy launch options** into Steam → Elden Ring → Properties → General.
   They include `dxgi,dinput8=n,b`, OpenXR runtime import, WiVRn IPC exposure and
   the Hub launch adapter. Connect WiVRn, keep Steam/game offline, and launch from
   Steam. This preview hides the generic Hub Launch game button for Elden Ring.
6. The adapter preserves Steam's selected Proton command, prefix and arguments,
   replacing the recognized game argument with this installation's
   `Game/eldenring.exe`. It changes no anti-cheat executable and renames no game
   file. Missing adapter code, unsupported command forms, changed loader binaries
   or unsupported game versions stop launch. If a protected/EAC launcher appears,
   quit and review the actual Steam options.

The native OpenXR session uses Proton's WineOpenXR/D3D12 bridge to WiVRn. No
UEVR injector, .NET dependency, R.E.A.L. VR or host xrizer selection is required
by this recipe. A selected host runtime does not prove that the bridge works.

## First gameplay checks

Title screens, menus, cutscenes and loading intentionally use cinema. Load an
offline save before checking headset rendering, stereo depth, head tracking,
both controllers, movement, interaction, inventory and combat. Return from the
menu and check immersion again. Record the actual result with **Record live
test…**, including the game/Proton version and any limitation.

Use **Controller bindings** for the complete sourced reference. These are the
archive's defaults, not a local gameplay pass:

| Input | Default action |
| --- | --- |
| Left / right stick | Move / turn |
| A / B / X / Y | Interact / dodge and sprint / use item / event and two-hand modifier |
| Left-stick click, tap | Crouch |
| Left-stick click held + tilt | D-pad: equipment, spell and item selection |
| Right-stick click | Lock on |
| Left menu, tap / hold ≥0.45 seconds | Menu / map |
| Left trigger / grip | Guard / skill |
| Right trigger / grip | Light / heavy attack; context changes with two-handing |

Physical weapon swings, shield posture, gripping a hilt with a free hand and
hand-directed casting are documented features needing local testing. Hold the
left stick still and click for about 0.5 seconds to toggle menu navigation
override. Despite its name, `LeftGripPlusStickIsDpad` is documented as **stick
click + tilt**, not grip + tilt.

Keep the initial `Enabled=true`, `VRRuntime=openxr`, `StereoMode=full` settings.
There is no in-headset ERVR settings menu in this release. Edit `ERVR.ini` only
after establishing a baseline; leave diagnostic/address settings alone.

## Diagnostics and restoration

**Log diagnostics** discovers `Game/ERVR/ERVR.log` and `Game/ReShade.log`.
OpenXR-backend or add-on-registration messages are historical loading evidence;
they do not verify current rendering or controls. Keep compatibility scans,
log evidence and local gameplay test records distinct.

**Remove mod** restores recorded original files. Edited text settings are kept
in the Hub backup's `user-modified` folder. Changed binaries stop removal for
review. Untracked logs/cache remain. Saves are not installation targets.
ERVR itself may change the prefix's `GraphicsConfig.xml` and create
`GraphicsConfig_ervr_backup.xml`; those runtime changes are outside the Hub's
file transaction and may need manual restoration.

## Inspected payload

- ERVR V0.4.0 ZIP SHA-256:
  `851221c337d2a365df547b34435246486f4e390a77999b1fe712e764ef33a21a`
- Ten files: the two root loader DLLs, ReShade config/license, and ERVR's DLL,
  config, README, changelog, license and third-party notice.
- Bundled ReShade DLL SHA-256:
  `0cee63f9c9f13f3ac909c5b4903f4dbb4b719a7ab3b4f13b0deaf83c814b94f7`
  matches the archive's own notice. This is not independent upstream attestation.
- The author's linked GitHub repository returned 404 during review. The Hub
  bundles no mod binaries; new archives require a recipe review and updated pin.

The source ZIP includes a patch from dev6 and `SHA256SUMS`.
