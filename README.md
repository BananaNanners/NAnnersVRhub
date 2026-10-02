# NAnnersVRhub 0.3.0

A Linux VR mod hub for Steam games, developed on CachyOS + WiVRn + Quest 3.

## Recommended development install

From this folder:

    python -m pip install -e .

Then launch the GUI with:

    nannersvrhub

CLI commands still work through the same launcher, for example:

    nannersvrhub status
    nannersvrhub verify cyberpunk-2077
    nannersvrhub diagnose cyberpunk-2077

There is also an explicit CLI entry point:

    nannersvrhub-cli status

Running directly from the source tree remains supported:

    python -m vrhub.gui
    python -m vrhub.cli status

The GUI needs PySide6 (`sudo pacman -S pyside6` on CachyOS/Arch).

## 0.3 reliability changes

Game-root installs are staged and validated before the game is touched. During the copy phase, files that already exist are backed up for the duration of the transaction; if a copy fails, NAnnersVRhub restores the original files and removes files created by the failed transaction.

ZIP member paths are normalized before directory detection, so Windows-created archives using `\` separators work correctly on Linux. Components can also declare `required_files` sentinels; CyberpunkVR Port now requires `red4ext/plugins/CyberpunkVR_Stereo/CyberpunkVR_Stereo.dll`, preventing the incomplete 54-file package from being accepted as the full VR port.

A paste-friendly diagnostic summary is available from **Copy diagnostics** in the GUI or:

    nannersvrhub diagnose cyberpunk-2077

Local install/rollback events are written to:

    ~/.local/share/vrhub/vrhub.log

## Existing commands

    python -m vrhub.cli status
    python -m vrhub.cli install ready-or-not --file ~/Downloads/<mod>.zip
    python -m vrhub.cli install fatekeeper --file ~/Downloads/UEVR_FK.zip
    python -m vrhub.cli install-profile fatekeeper --file ~/Downloads/SLASHER-Win64-Shipping.zip
    python -m vrhub.cli launch-injector fatekeeper
    python -m vrhub.cli info fatekeeper
    python -m vrhub.cli updates
    python -m vrhub.cli mark-current fatekeeper
    python -m vrhub.cli verify cyberpunk-2077
    python -m vrhub.cli nexus-key

Each game is a recipe in `recipes/*.toml`.

## Launch guard

For games with a component checklist, the Steam launch options start with `vrhub-check`. It runs `verify` before the game and refuses to start it if a required mod is missing or damaged. Set `VRHUB_SKIP_CHECK=1` at the start of the launch options to bypass it.

## Tests

Run the regression suite with:

    python -m unittest discover -s tests -v

See `CHANGELOG.md` for release notes.
