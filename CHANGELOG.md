# Changelog

## 0.3.0 — reliability foundation

- Fixed ZIP handling for Windows-created archives whose directory entries use backslashes.
- Added rejection of duplicate normalized ZIP paths.
- Added transactional game-root installs: existing files are backed up and restored if any copy fails.
- Added per-component `required_files` sentinels and wired CyberpunkVR Port to require `CyberpunkVR_Stereo.dll`.
- Added recipe-configurable `root_dirs` support for future game-root installers.
- Added a local JSON-lines diagnostic log at `~/.local/share/vrhub/vrhub.log`.
- Added `diagnose` CLI output and a GUI **Copy diagnostics** button.
- Added a unified `nannersvrhub` launcher: no arguments opens the GUI; arguments go to the CLI.
- Added `nannersvrhub-cli` as an explicit CLI command.
- Added regression tests for Windows-path ZIPs, incomplete component archives, required-file verification, and rollback.
