# NAnnersVRhub 0.5.1

Final source build prepared from the accepted 0.5.1-rc1 installer candidate.
The runtime change from RC1 is the version label. The 0.5.0 compatibility and
diagnostics feature set is included; 0.5.1 adds a per-user desktop installation,
explicit local upgrades and application rollback.

## Installation and upgrades

- Run `python install.py` from the extracted source folder. Python 3.11+ and
  working PySide6 are required. The Hub installer uses no sudo, pip or network.
- Open the application-menu entry or `~/.local/bin/nannersvrhub`.
- App versions live under `~/.local/share/nannersvrhub/releases/`, with stable
  launchers and one active-version record. An absolute XDG_DATA_HOME relocates
  application/desktop files, without moving existing Hub state/history.
- Install a newer extracted source folder with the same command. Close the
  Hub first. The previous managed snapshot remains selectable via
  `~/.local/bin/nannersvrhub-manage rollback`; repeating it switches back.
- Dependency/resource checks and preparation happen before activation. Existing
  conflicting launchers, corrupt records and changed rollback files are
  reported and preserved. Automatic app downloads are outside this release.
- All four recipes now live in the Python package. Regular wheels include the
  recipes, icon and app/CLI/guard/manager entry points. The source installer is
  the recommended desktop workflow.

## Existing data and game workflows

Existing state, local gameplay tests, mod backups and logs remain under their
existing paths, including VRHUB_STATE overrides. The app installer does not
rewrite game files, Steam options, Proton selections or runtime configuration.

New managed launch options use a stable Steam guard path. Existing Steam guard
references are not automatically migrated; retain their source folders until
you review and replace those paths. See INSTALL-0.5.1.md.

The four workflows and dated gameplay references remain intact. Fatekeeper's
tested path is **2D Screen Mode OFF**, then close its in-game UEVR overlay with
**Insert**. CyberpunkVR Port remains experimental: keep the tested panels off
and close F10; opening the game menu caused passthrough, and exiting restored
full VR in the reported test. This release does not repair upstream rendering.

## Compatibility and diagnostics included from 0.5.0

The VR System dashboard, read-only WiVRn connection telemetry, four per-game
compatibility profiles, explicit gameplay history, bounded log diagnostics and
combined text/JSON support exports are included. Configuration findings,
historical logs and user-reported gameplay evidence remain separate. Readable
times use local 24-hour display; JSON retains source timestamps and offsets.
Review support exports before sharing; home-path replacement is not complete
anonymization. See RELEASE-NOTES-0.5.0.md and TROUBLESHOOTING.md for details.

## Validation and acceptance

- 237 unit tests passed from the final extracted source archive.
- Per-user deployment with real PySide6, independent source-folder removal,
  custom XDG/quoted paths, data preservation, failed activation and independent
  rollback recovery were tested in isolated fixtures.
- Actual RC1 -> final install, reinstall, rollback to RC1 and return to final
  preserve synthetic saved data in an isolated real-Qt environment.
- Wheel resources/entry points and source packaging were checked; release
  patches reproduce the exact final source files.
- On October 18 at 21:42 PDT, the user confirmed independent installed startup,
  all four games listed and two unspecified games running as expected.
- At 21:50 PDT, the user replied **"I'ts a pass!"** to the RC1 upgrade/rollback/
  return procedure. This is aggregate user-reported acceptance, not an invented
  new per-game test record.

No history migration or report-schema change is introduced. The historical
candidate procedure remains in RELEASE-CANDIDATE-0.5.1.md. GitHub publication is
a separate step after the prepared source is reviewed and merged.
