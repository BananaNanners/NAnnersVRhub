# NAnnersVRhub 0.5.2

This release adds in-app Hub downloads/upgrades and Hogwarts Legacy for
Heroic/Epic, alongside the four existing game workflows.

## Hub updates

Open **Hub updates… → Check now** to check the official stable GitHub release.
Choose **Download source ZIP**, then **Install update…** and **Restart Hub**.
Downloads are checked against the release SHA256SUMS and GitHub asset digest
when supplied, then rechecked before installation. Startup checks run at most
once per 24 hours; automatic downloads are optional and off by default.
Installation and restart require your action.

The updater accepts published stable releases from this project only. Drafts,
prereleases and older versions cannot be installed through this workflow.
0.5.1 users must install 0.5.2 once with `python install.py`, because 0.5.1 does
not include the updater. Existing 0.5.2 development builds can update directly
to the published 0.5.2 stable release.

## Hogwarts Legacy

- Discover the Epic installation, prefix and selected runner from Heroic.
- Install the matching HL_UEVR v2.0.6 injector and full game profile, including
  scripts, plugins, data and model files. The Hub does not bundle the mods.
- **Run UEVR injector** opens the injector in the existing prefix using native
  Heroic's selected runner. Select the HogwartsLegacy process, OpenXR and Inject
  in UEVR. Flatpak and unsupported layouts retain Heroic's manual route.
- Keep shader loading complete and close the in-game UEVR overlay with Insert
  before evaluating immersion. Existing profile backups remain separate from
  Hogwarts game saves.

On October 19, the user reported SUCCESS with the dev4 one-click launch and
passed rendering, head tracking, controller input and stereo depth. A few
minutes of follow-up gameplay also confirmed spell drawing and wrist-flick
activation. This reference describes CachyOS, native Heroic, WiVRn, Quest 3
and the saved Proton-CachyOS-latest runner selection; its exact build version
was not captured. Voice, body tracking, other gestures and longer-session
stability remain untested. Local gameplay records retain their original
configuration snapshots.

## Install and recovery

Requires Linux, Python 3.11+ and working PySide6 in the installation Python.
For manual installation, close the old Hub, extract the attached custom source
ZIP and run `python install.py`. Launch from the application menu or
`~/.local/bin/nannersvrhub`. The Hub installer does not install system/Python
dependencies, game mods, runners or runtime packages automatically.

After an upgrade, close the Hub before using
`~/.local/bin/nannersvrhub-manage rollback`. Repeat rollback to return to the
other managed version. Existing game installations, mod records, saves, backups
and local gameplay history stay in place.

The four existing game workflows retain their known conditions: Skyrim uses
the MO2 shortcut's prefix and one enabled MGO OpenComposite variant; Fatekeeper
needs 2D Screen Mode off and the UEVR overlay closed; Ready or Not follows its
DX11/U/Home route; CyberpunkVR remains experimental with the reported menu
passthrough limitation.

See [UPDATE-TESTING-0.5.2.md](UPDATE-TESTING-0.5.2.md) for the dev4-to-stable live
update check. Automated release checks and their actual results are supplied in
the maintainer release kit; the prepared build is not a published GitHub release
until publication is completed.
