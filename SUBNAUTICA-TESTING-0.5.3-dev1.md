# Subnautica preview — 0.5.3-dev1

This is the historical dev1 setup/test guide. For the accepted live result and
preferred stock controls, see [Subnautica success and controls](SUBNAUTICA-SUCCESS-0.5.3-dev2.md).


Steam Subnautica (app 264710), Windows/Proton, default branch. This is the original
Subnautica, not Below Zero. Uses SubmersedVR, WiVRn and xrizer. No UEVR injector or
UEVR Desktop Runtime installer is used by this recipe. Local gameplay remains
UNVERIFIED until a user records a live test.

## Upgrade the Hub

Close the old Hub and save the ZIP in Downloads. In fish:

```fish
unzip -n ~/Downloads/NAnnersVRhub-0.5.3-dev1-source.zip -d ~/Downloads
and cd ~/Downloads/NAnnersVRhub-0.5.3-dev1
and python install.py
and ~/.local/bin/nannersvrhub
```

Use the existing Python/PySide6 installation. Verify all six games appear and the
five existing games retain their installation records and test history. Existing
game saves are outside this Hub upgrade. Keep this development preview separate
from the stable GitHub release; it is not an automatic update-channel promotion.

## Install the author releases

1. In Steam, use the default Subnautica branch, select a Proton build and launch
   the plain Windows game once. Close it before mod installation.
2. Download these exact **release assets**, not Source code ZIPs:
   - [Tobey's pack v5.4.23-pack.3.1.1](https://github.com/toebeann/BepInEx.Subnautica/releases/tag/v5.4.23-pack.3.1.1): `Tobey.s.BepInEx.Pack.for.Subnautica.zip`.
   - [SubmersedVR 0.2.1](https://github.com/Okabintaro/SubmersedVR/releases/tag/0.2.1): `SubmersedVR_0.2.1.zip`.
3. Remove older VR Enhancements / SN1MC Motion Controls mods using their existing
   installer first. The Hub detects two known DLL names, not every mod conflict.
4. Select Subnautica in Games, click **Install mod file…**, then select **both ZIPs
   together**. Renamed downloads are accepted if their bytes match. The Hub
   installs all Windows loader files and all nine SubmersedVR files, including
   action/binding JSONs. The loader's two macOS files are skipped.
5. Run **Verify** and **Compatibility report**. Read the guide's author links.
   A file pass does not establish loaded plugins or actual VR gameplay.
6. Select xrizer as host OpenVR adapter. Connect the headset through WiVRn.
   Click **Copy launch options** and put the result in Steam Properties -> General.
   It includes `winhttp=n,b`, OpenXR runtime import, WiVRn `comp_ipc` exposure and
   `-vrmode openvr`. Keep the generated guard in the copied result. The Hub does
   not edit Steam settings. Review/merge existing options instead of losing them.
7. Launch through Steam, selecting VR if asked. No injector is needed.

The [author's Linux setup](https://github.com/Okabintaro/SubmersedVR#linux-setup)
reports WiVRn + Quest 3 + xrizer. It also describes unreliable trigger interaction;
try **A** for interaction if necessary. This is upstream guidance, not a local test.

## First live test

Load a save and test full headset rendering, stereo depth, head tracking, both
controllers, movement/turning, tool aiming, pickup/use, and PDA/inventory return.
Record the result in **Record gameplay test**. Include Proton build and any
interaction workaround in the notes. A short pass does not test an entire playthrough.

If the game stays flat or controls fail, save **Compatibility report** and
**Game log diagnostics**. Automatic discovery reads `BepInEx/LogOutput.log`.
Choose another log explicitly if needed. Known OpenXR signatures are historical
evidence; a clean scan cannot certify successful plugin loading or immersion.

## Backups, removal and recovery

The installer verifies both archive digests and plans all targets before game writes.
It backs up overwritten files under the Hub data folder's `backups/subnautica-*`
entry. The obsolete `BepInEx/patchers/Tobey` folder is backed up and retired,
as directed by the current loader release. Unrelated plugins and game saves
are not install targets. Do not install or remove mods while the game is running.

Use **Uninstall mod** before replacing a Hub-recorded install. Removal restores
original files and the retired patcher folder. Changed `.cfg`, `.ini`, `.json`
and `.txt` files are first copied to the backup's `user-modified` folder.
Backups remain available after removal. Unrecorded runtime logs/cache files remain.
If an installed binary changed, or an original backup is missing, removal stops
before changing game files. Preserve the report/backup and review the Steam or
mod update before restoring old DLLs; do not delete the inventory to force removal.

To roll the Hub application back, close it and run:

```fish
~/.local/bin/nannersvrhub-manage rollback
```

Repeating the command returns to the preview. Hub rollback switches application
code; it does not uninstall Subnautica mods. Remove those through this preview
first if desired. Older Hub builds do not contain the Subnautica recipe.
