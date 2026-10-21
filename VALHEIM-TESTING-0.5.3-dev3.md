# Valheim / VHVR preview — 0.5.3-dev3

Adds a seventh recipe for Steam Valheim's Windows build under Proton, using
WiVRn and xrizer. Valheim gameplay is **UNVERIFIED locally**. The six earlier
recipes keep their evidence and workflows, including Subnautica's dated success
and preferred stock controls. No UEVR injector is used for Valheim.

## Upgrade the Hub

Close the old Hub. Save the ZIP in Downloads and run in fish:

```fish
unzip -n ~/Downloads/NAnnersVRhub-0.5.3-dev3-source.zip -d ~/Downloads
and cd ~/Downloads/NAnnersVRhub-0.5.3-dev3
and python install.py
and ~/.local/bin/nannersvrhub
```

Check that all seven games appear and existing test histories remain intact.
Existing mod installations and saves do not need to be reinstalled for this Hub
upgrade. This is a development preview, not a stable GitHub publication or an
automatic update-channel promotion.

## Valheim prerequisites

1. In Steam -> Valheim -> Properties -> Compatibility, force your selected Proton
   build. Launch the plain Windows game once, then close it. The Hub requires
   `valheim.exe`, `valheim_Data` and the game's own prefix (app 892970). It does
   not install this Windows payload into a native Linux-only copy or a server.
2. Review your Valheim version. VHVR 0.11.0 documents game **1.0.15–1.0.17**.
   The selected 0.11.2 follow-up does not name a new compatibility range. Other
   versions need review; the Hub does not infer compatibility from Steam build IDs.
3. Review existing mods before the first test. A mod-manager installation with a
   second `ValheimVRMod.dll` must be removed through its owner first. The Hub
   retains unrelated plugins and does not certify modpack compatibility.

## Download and install both exact archives

- [VHVR v0.11.2](https://github.com/brandonmousseau/vhvr-mod/releases/tag/v0.11.2):
  download the **vhvr.zip** asset, not Source code.
- [BepInExPack Valheim 5.4.2351](https://thunderstore.io/c/valheim/p/denikson/BepInExPack_Valheim/v/5.4.2351/):
  choose the manual ZIP download. It is normally named
  **denikson-BepInExPack_Valheim-5.4.2351.zip**.

Select Valheim in the Hub, choose **Install mod file…** and select **both ZIPs
together**. Hashes identify the inspected pair even if a browser renames the files.
A newer/different archive needs recipe review. Mods are not bundled in the Hub ZIP.

The loader's `BepInExPack_Valheim` wrapper is stripped. Its Windows payload is
installed, excluding package metadata/documentation and Linux/macOS startup
files. All VHVR files are installed, including its Unity XR subsystem, assets,
controller JSONs and optional bHaptics data. Archive `Valheim_Data` is mapped to
the Windows game's `valheim_Data`, avoiding a separate directory on Linux.
The installer checks target paths/case collisions before writes and records
backups of existing files under the Hub data folder.

## WiVRn launch

1. Connect the Quest through WiVRn and keep xrizer selected as host OpenVR adapter.
2. Click **Copy launch options** and put the complete result in Steam Properties
   -> General. Preserve/merge any existing options deliberately. The copied
   text includes the inventory guard, `winhttp=n,b`, runtime import and WiVRn IPC
   exposure, then these game/mod arguments:

   ```text
   -force-d3d11 -flatScreenMode=false -ModEnabled=true -UseVRControls=true -UseOverlayGui=false
   ```

3. Use Steam's ordinary **Play Valheim** route with Proton/Direct3D 11 for the first
   test. Avoid the Vulkan launch choice. Valheim does not use Subnautica's separate
   Steam VR Mode launch entry.

VHVR's `flatScreenMode` defaults to `auto`, which checks whether SteamVR is already
running. That check does not establish WiVRn readiness. Its upstream
`-flatScreenMode=false` override requests VR without that process gate;
initialization can still fail and fall back to flat mode. The other flags request
the mod, motion controls and the controller-compatible GUI. The Hub supplies
copyable launch text; it does not rewrite Steam settings or the VHVR configuration.
Do not change `flatScreenMode` to an invented enum value: the accepted upstream
strings are `auto`, `false` and `true`.

## First gameplay test

Load a character/world and test full VR rendering, head tracking, stereo depth,
both controllers, locomotion/turning, inventory, tools, building and combat. Use
the in-game Compendium for current motion-control guidance. Record the outcome
with your actual game/Proton version and any issues. Gestures, multiplayer, voice,
full-body tracking, bHaptics and long-session stability remain unverified unless
separately tested. Installed optional files alone do not verify those features.

If the game stays flat or input fails, collect **Compatibility report** and
**Game log diagnostics** immediately after that test. Automatic log discovery
reads `BepInEx/LogOutput.log`; choose another file explicitly if needed. No known
signature does not imply a clean startup or a gameplay pass.

## Removal and rollback

Close Valheim before installing/removing mods. Use **Uninstall mod** before
replacing a recorded Hub install. Removal restores original files. Changed text
settings are saved in the backup's `user-modified` folder; edited binaries or
missing/corrupted original backups stop removal for review. Other plugins,
generated logs/config files and Valheim worlds/characters are not deleted.

The Hub does not migrate or edit game saves/Steam Cloud data. Keep your normal
Valheim save backups. The Subnautica-only obsolete Tobey patcher retirement is
not applied to Valheim's unrelated patcher directories.

To switch the Hub application back, close it and run:

```fish
~/.local/bin/nannersvrhub-manage rollback
```

Repeating returns to the preview. Application rollback does not uninstall game
mods. If desired, remove VHVR through dev3 first; dev2 has no Valheim recipe.

VHVR updates are checked on GitHub. Review loader updates on its Thunderstore
page manually. Both pins require inspection before installation of newer releases.

## Source references

- [VHVR release notes and version history](https://github.com/brandonmousseau/vhvr-mod/releases)
- [VHVR configuration and launch-option parser at v0.11.2](https://github.com/brandonmousseau/vhvr-mod/blob/v0.11.2/ValheimVRMod/Utilities/VHVRConfig.cs)
- [VHVR project requirements](https://github.com/brandonmousseau/vhvr-mod)
- [Valheim loader package and manual install instructions](https://thunderstore.io/c/valheim/p/denikson/BepInExPack_Valheim/v/5.4.2351/)
- [Unity player command-line arguments](https://docs.unity3d.com/Manual/PlayerCommandLineArguments.html)
