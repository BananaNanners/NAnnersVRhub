# Hogwarts Legacy — 0.5.2-dev2 desktop test

Historical Steam-only preview. The user's copy is Heroic/Epic; use
[HOGWARTS-HEROIC-0.5.2-dev3.md](HOGWARTS-HEROIC-0.5.2-dev3.md) for the corrected
current workflow. The acceptance steps below describe the superseded preview.

Development build; not a GitHub release. The accepted dev1 Hub-update controls
remain available. Hogwarts gameplay evidence starts **UNVERIFIED**.

## Install the Hub

Close the Hub first, then run in fish:

```fish
unzip -n ~/Downloads/NAnnersVRhub-0.5.2-dev2-source.zip -d ~/Downloads
and cd ~/Downloads/NAnnersVRhub-0.5.2-dev2
and python install.py
and ~/.local/bin/nannersvrhub
```

Confirm five games are listed and the existing test history is present. This is
a manual preview upgrade; dev1's recovery manager expected four recipes. Dev2
removes that fixed-count limitation for future updates and keeps the new manager
available when rolling the application back. `nannersvrhub-manage rollback`
switches to the previous installed app; repeating returns to dev2. Recipe changes
do not delete saved records for games absent from an older application version.

## Install the VR files

This recipe targets the **Steam version**, AppID **990080**. Launch it once with
your existing Steam-selected Proton build to create its prefix. The Hub does not
choose a different Proton version or alter Steam options automatically.

Use the [HL_UEVR v2.0.6 author release](https://github.com/jbusfield/HL_UEVR/releases/tag/v2.0.6).
Download both release assets below; leave them as ZIPs. Do not use GitHub's
generated Source code ZIP or an older Nexus profile for this first test.

| Author asset | Hub action | Destination inside the game's Proton prefix |
| --- | --- | --- |
| UEVR.zip | Install mod file… | drive_c/uevr/ |
| HogwartsLegacy.zip | Install profile… | drive_c/users/steamuser/AppData/Roaming/UnrealVRMod/HogwartsLegacy/ |

The author provides the injector/backend pair together. Use this pair for the
first test. The profile contains scripts, data, native plugins and models; the
Hub installs the full archive. It backs up an existing untracked VR profile
before replacing it, avoiding a merge with old profile contents. A Hub-recorded
profile must first be removed using **Remove profile**. That can restore the
earlier backup. These folders are separate from Hogwarts save games.

Copy/review the recipe's launch options in Steam. They include runtime import:
`PRESSURE_VESSEL_IMPORT_OPENXR_1_RUNTIMES=1`. Review Frame Generation/HDR settings
using the displayed setup guide. If the injector requests a Windows .NET runtime,
the guide includes its prefix-specific install command. The Hub does not scan or
install that dependency for you.

## First live test

1. Connect the headset through WiVRn. Launch Hogwarts Legacy from Steam and wait
   for shader loading to finish before injecting from the main menu.
2. Choose **Run UEVR injector**, select the HogwartsLegacy process and **OpenXR**,
   then inject. Load an actual save.
3. Close the in-game UEVR overlay with **Insert**. If it is a floating screen,
   review **2D Screen Mode OFF** before assessing immersion. This is a setup check,
   not a confirmed Hogwarts-specific fix.
4. Test full VR rendering, head tracking, stereo depth, moving/turning, wand aim
   and casting. Open/close game menus and confirm the scene returns correctly.
   Optional voice, gesture and body features need separate checks; none is
   certified as working on Linux by this build.
5. Use **Record live test…** with explicit results and notes. If something fails,
   use **Log diagnostics…** and **Create support report…**. Automatic log selection
   looks for `UnrealVRMod/HogwartsLegacy/log.txt` in this game's prefix; select
   another log explicitly if this UEVR build logs elsewhere.

Compatibility may remain **REVIEW REQUIRED** even with all inventories present,
because injection settings and actual gameplay remain manual checks. Presence
does not certify DLL/model loading, file versions or controller operation.

## Source and validation record

Maintainer release inspected October 19, 2026:

| Asset | Bytes | GitHub SHA-256 |
| --- | ---: | --- |
| UEVR.zip | 42,144,999 | abd879030cb103ce7669b76026547b9cc0f811a8531dc9f09cd558b5baadcbd0 |
| HogwartsLegacy.zip | 39,324,504 | 30d7e626882bb3a7e1d04d8a42fd4f4bbcda9011054c4b12bf9e6e722dab06a3 |

Both official downloads matched these digests. Isolated installation copied all
**10 injector files** and **192 profile files**, with every extracted byte checked
against the archives. Existing VR profile replacement/restore and a synthetic
save-file preservation check passed. This did not run the Windows injector or
game and is not gameplay evidence. Mod archives are not included in the Hub ZIP.

Validation also passed **277 tests with PySide6**, including the new Hogwarts
workflow and the existing application updater. A real managed dev1 -> dev2
upgrade, rollback to the four-game application and return to the five-game
application preserved existing state/history bytes. The new game's history
remained empty. The official older 0.5.1 source archive still passed download
verification and remained blocked as a downgrade.

Primary references: [author release and requirements](https://github.com/jbusfield/HL_UEVR/releases/tag/v2.0.6),
[profile controls](https://github.com/jbusfield/HL_UEVR),
[UEVR setup](https://docs.uevr.io/),
[Windows .NET 6](https://dotnet.microsoft.com/en-us/download/dotnet/6.0).
