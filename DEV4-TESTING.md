# NAnnersVRhub 0.5.0-dev4 testing

Dev3-fix1 passed local checks and a user-reported Skyrim VR/MGO launch/controller
test on October 17. Dev4 adds compatibility profiles for the other three existing
games and keeps that Skyrim result as the dated reference.

## Run

Extract the ZIP in Downloads, then run in fish:

```fish
cd ~/Downloads/NAnnersVRhub-0.5.0-dev4
python -m unittest discover -s tests -v
python -m vrhub.gui
```

Use existing PySide6. No new dependency, automatic install, Proton change, or
Steam/MO2 edit is needed to run the reports.

## Test one game at a time

Start with **Games -> Fatekeeper -> Compatibility profile -> Refresh
compatibility -> Copy compatibility report**, then paste the report for review.
The same actions are available for Ready or Not and Cyberpunk 2077.

| Game | New local evidence | Gameplay label |
| --- | --- | --- |
| Fatekeeper | Recorded Proton, UEVRInjector.exe/UEVRBackend.dll, profile config, Hub file inventories for the UEVR build and game profile, protontricks-launch | UNVERIFIED |
| Ready or Not | Recorded Proton and recorded VRO .pak files under this install's Paks directory | UNVERIFIED |
| Cyberpunk 2077 | Recorded Proton, native VR-plugin file, component file inventories, and phase-2 VR-port installation | EXPERIMENTAL |
| Skyrim VR/MGO | Existing MO2/adapter/conflict checks, with the October 17 live test reference | USER-REPORTED LIVE TEST |

Gameplay labels describe recorded evidence, independently of local-check status.
Files being present never promote an unverified game to a tested game.
No new gameplay reference or tested Proton version has been invented for the
three added profiles.

### Reading the new reports

- **REVIEW REQUIRED** is expected when the new games' measured file checks pass:
  Steam options, injector selection and some in-game settings still need manual
  review. Each report names them. The Hub's environment is not proof of a game's
  Steam options.
- **INCOMPLETE** means evidence is missing, such as an unresolved recorded Proton
  path or absent Hub install inventory. Manual installs may be valid but cannot
  be fully inventoried by this report. Do not reinstall a working game merely
  to change this status.
- **NOT READY** means a checked file requirement failed, such as a missing
  injector/backend, lost recorded profile plugin, missing VRO package, or missing
  Cyberpunk VR port.
- A record pointing to another library/prefix, an escaped symlink, or a directory
  with a file's name cannot satisfy the current installation checks.

Cyberpunk's ordinary preflight deliberately allows base-game setup before the
phase-2 VR port is installed. Dev4's **compatibility** report also requires the
VR port; it cannot certify VR installation from the base-game guard alone.
The existing base-game launch guard retains its behavior.

Recorded Proton is taken from this prefix's config_info when its existing path
can be resolved. It is not a live-process check or proof of the currently selected
Steam tool. The scan does not guess a replacement from other installed tools.

Fatekeeper's inventory checks all files recorded during Hub installs, including
any recorded plugin files. It does not compare with a release download. The .NET
Desktop Runtime, DLSS Frame Generation setting and OpenXR injector selection are
manual-review items. Ready or Not's renderer, VRO arguments and mission VR
transitions remain manual checks. Cyberpunk's versions, DLL override, loader
behavior and actual VR rendering remain manual checks.

After reviewing each report, follow that game's existing setup guide and test
actual gameplay on your headset. Report VR rendering, controllers, and any
failure separately. Keep the working Skyrim/MGO selection unchanged.

CLI equivalents:

```fish
python -m vrhub.cli compatibility fatekeeper
python -m vrhub.cli compatibility ready-or-not
python -m vrhub.cli compatibility cyberpunk-2077 --json
```

JSON compatibility schema stays at version 1 with additive optional metadata:
`validation`, `manual_checks`, and `checks`. Exit 0 covers LOCAL CHECKS PASSED
and REVIEW REQUIRED; other statuses exit 1. Diagnostics includes the selected
game's compatibility report. VR System's scan schema remains version 2.

## Existing development checkout

Choose one patch from the archive:

- `dev4-from-dev3-fix1.patch`: from the delivered 0.5.0-dev3-fix1 source.
- `dev4.patch`: cumulative update from clean v0.4.0 (`2e320ac`).

From your existing dev/0.5.0 repository, for dev3-fix1:

```fish
git status --short
git apply --check ~/Downloads/NAnnersVRhub-0.5.0-dev4/dev4-from-dev3-fix1.patch
git apply ~/Downloads/NAnnersVRhub-0.5.0-dev4/dev4-from-dev3-fix1.patch
python -m unittest discover -s tests -v
python -m vrhub.gui
```

Preserve unrelated local changes. If the check fails, stop and share the error.
For clean v0.4.0, substitute dev4.patch. Do not apply both. Testing the standalone
source requires no repository changes.

## Validation before delivery

- 122 unit tests pass, including complete local file/state fixtures for all new
  workflows and the existing Skyrim Unleashed regression cases.
- Covered missing injectors/backend/profile files, missing recorded plugins,
  untracked arbitrary PAKs, wrong file types/locations, escaped symlinks,
  phase-2 Cyberpunk omission, empty inventories, missing recorded Proton,
  manual-review evidence, schema/path validation, CLI JSON and diagnostics.
- Reports are read-only and start no processes in the filesystem-fixture tests.
- Qt smoke checks pass for all four profiles, evidence labels, clipboard output,
  missing-file refresh, tab switching, close, and Skyrim's retained local pass.
  The rendered profile view was inspected.
- Incremental/cumulative patches reproduce the final source; the extracted
  archive passes the tests.
- Live dev4 testing of the new game profiles remains on the user's machine.
