# NAnnersVRhub 0.4.0 development

A Linux VR mod hub for Steam games, developed on CachyOS + WiVRn + Quest 3.

Current recipes: Cyberpunk 2077, Fatekeeper, Ready or Not, and the first Skyrim VR / Mad God's Overhaul workflow.

## Install for development/testing

From this folder:

    python -m pip install -e .

Launch the GUI:

    nannersvrhub

The GUI needs PySide6 (`sudo pacman -S pyside6` on CachyOS/Arch).

## 0.4.0 additions

### Game-handler architecture

Most games remain completely recipe-driven. Games that need special Linux/VR checks can now opt into a small handler with:

    handler = "skyrim-vr"

Game-specific behavior lives in `vrhub/handlers.py`, rather than adding Skyrim/Cyberpunk/etc. branches throughout `hub.py` and `gui.py`. The first handler hooks are:

- extra preflight checks;
- game-specific notes;
- whether a recipe supports direct archive installation.

A new `method = "guide"` workflow is available for setups that should be validated by the hub but remain owned by another installer.

### Skyrim VR + Mad God's Overhaul

The `skyrim-vr-mgo` recipe is a guided integration. Jackify/Wabbajack remains responsible for installing/updating MGO; NAnnersVRhub checks and launches the surrounding Linux VR stack.

Run:

    nannersvrhub preflight skyrim-vr-mgo

By default it checks Skyrim VR discovery, the Proton prefix and WiVRn. It also auto-detects common MGO directories by looking for `ModOrganizer.exe`. If auto-detection does not find yours, override it before launching the hub:

    set -x NANNERS_MGO_DIR "/path/to/your/MGO"
    nannersvrhub

The Skyrim handler checks for `ModOrganizer.exe` and MGO's bundled `Open Composite XR - Incompatible with VR Performance Kit` directory. The GUI exposes **Launch MO2**, which starts the Jackify-created non-Steam shortcut through Steam, plus **Launch Skyrim VR**. In dev6 the game action first ensures the real Jackify MO2 shortcut is running, then forwards MO2's configured SKSEVR/SKSE entry through a short-lived MO2 process in that shortcut's own Proton prefix. The Hub reads the active MO2 profile and executable list from `ModOrganizer.ini` without editing it. Bridge status is written to `~/.local/share/vrhub/mo2-bridge.log`. Configured VR Performance Kit directories are reported as an informational warning because enabled/disabled state is MO2-profile-specific.

This workflow is built around WiVRn + xrizer + MGO's bundled OpenComposite. It does not replace Jackify and does not copy or redistribute the MGO modlist.

### Preflight

Recipes can declare runtime requirements. Check a game without changing anything:

    nannersvrhub preflight cyberpunk-2077

The GUI has the same **Preflight** action. It checks the Steam install, Proton prefix, OpenXR/WiVRn state, required component readiness, plus any game-handler checks.

### Inspect an archive before installing it

For game-root recipes such as Cyberpunk, inspect an archive without touching the game:

    nannersvrhub inspect cyberpunk-2077 --file ~/Downloads/<archive>.zip

The report shows which component was detected, how many files are in the archive, how many would actually be installed, which game-root trees are targeted, required sentinels, and sample destinations.

### Validated recipes

Recipe TOML is validated at startup. Bad app IDs, duplicate components, unsafe sentinel paths, unknown handlers, unsupported methods, malformed links and malformed requirements are rejected before install work begins.

## Existing useful commands

    nannersvrhub status
    nannersvrhub verify cyberpunk-2077
    nannersvrhub diagnose cyberpunk-2077
    nannersvrhub preflight skyrim-vr-mgo
    nannersvrhub updates
    nannersvrhub nexus-key
    nannersvrhub install ready-or-not --file ~/Downloads/<mod>.zip
    nannersvrhub install fatekeeper --file ~/Downloads/UEVR_FK.zip
    nannersvrhub install-profile fatekeeper --file ~/Downloads/SLASHER-Win64-Shipping.zip
    nannersvrhub launch-injector fatekeeper
    nannersvrhub launch-tool skyrim-vr-mgo
    nannersvrhub launch-game skyrim-vr-mgo

## 0.4.0 release-candidate scope

The public game list is intentionally limited to VR workflows that have been verified end-to-end on the test system:

- Cyberpunk 2077
- Fatekeeper
- Ready or Not
- Skyrim VR / Mad God's Overhaul

The experimental DOOM (2016) GOG/Heroic + KHARVOX recipe is not shipped in the public recipe list because the KHARVOX intro and game launch worked but actual DOOM gameplay did not enter native stereo VR on the tested Proton/WiVRn path. The Heroic/GOG support code remains in the source tree as development groundwork for a future verified integration.

## Tests

    python -m unittest discover -s tests -v

See `CHANGELOG.md` for development notes.


## Generic Steam launching (dev9)

For Cyberpunk 2077, Fatekeeper, and Ready or Not, **Launch game** asks Steam to launch the app through `steam://launch/<appid>/dialog`. This intentionally leaves renderer selection and other launch choices to Steam. If a game is set to **Ask when starting game**, Steam can show its normal chooser; if a default choice is saved, Steam uses it. NAnnersVRhub does not add DX11/DX12/Vulkan flags on this path.

## 0.4.0-dev8 UI

The Qt GUI now uses the BananaNanners visual theme derived from the project/channel artwork, with a branded header, dark panels, yellow/blue accents, and live Skyrim/MO2 launch status.
