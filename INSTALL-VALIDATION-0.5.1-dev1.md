# 0.5.1-dev1 validation

This is an installer development build, not a newly published GitHub release.
No new game-rendering/controller result is implied by packaging tests.

## Automated coverage

- 237 unit tests: the existing 209 plus 28 installation/guard/desktop cases.
- Install/check, dependency failures, staged-version mismatch, conflicting or
  modified launchers, interrupted activation, locking, corrupt metadata and
  altered previous-version files.
- Existing state/history/backup bytes preserved across install, reinstall,
  upgrade, failure and rollback fixtures.
- Real PySide6 6.12.0 in an isolated Python 3.12 environment: source-folder
  independence, custom XDG paths, all four recipes, four synthetic saved-test
  histories, offscreen window and desktop-bootstrap startup.
- Explicit upgrade to a synthetic next-version source fixture, rollback in
  both directions and independent recovery from a broken active app import.
  That fixture is not a delivered dev2 release or gameplay evidence.
- Real GIO desktop-parser launch with spaces, percent, dollar, quotes,
  backticks and backslash in the application path. Generated Steam guard
  paths also round-trip as one literal shell argument.
- Non-editable wheel resources and console entry points checked outside the
  checkout; source-distribution recipe/installer/test files checked as well.
- Extracted delivery source/patch checks and full unit suite; installed/source
  support-report UI smoke checks preserve export/history behavior.

## Desktop checks still needed

Run the commands in INSTALL-0.5.1.md, open the new menu entry, confirm the version,
all four games and saved tests, then close the Hub and rename the new extracted
source folder. Reopen the menu entry to confirm the installed copy is independent.

Keep older source folders referenced by Steam guards. No existing Steam options
are automatically changed. First installation has no prior managed version to
roll back to; rollback becomes available after a second managed app snapshot.

This does not install system Python/Qt, download app updates, repair upstream
game/mod rendering issues or supply a new live VR gameplay test. The existing
Fatekeeper/Cyberpunk overlay guidance and Cyberpunk menu limitation remain.
