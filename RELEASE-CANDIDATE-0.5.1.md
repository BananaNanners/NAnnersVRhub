# NAnnersVRhub 0.5.1-rc1

Version-label-only runtime promotion of the tested dev1 installer build. The
installer, desktop/guard launchers, recipes, game workflows and data formats
remain unchanged.

Acceptance update: on October 18, 2026 at 21:50 PDT, the user replied
**"I'ts a pass!"** to the requested RC1 upgrade, rollback to dev1 and return to
RC1 check. This is aggregate user-reported acceptance of that procedure, with
no new per-game breakdown or automatic measurements. The procedure below is
retained as the historical candidate checklist. Final 0.5.1 promotes this accepted
runtime with only its version label changed.

## Dev1 desktop acceptance

On October 18, 2026 at 21:42 PDT (America/Los_Angeles), the user reported:

> It runs independently and all games are present also tested two games and they run as expected.

This confirms installed-source independence, all four recipes listed and two
user-reported game launches. The two titles and individual rendering/tracking/
input/stereo checks were not specified. No additional per-game SUCCESS entries
or gameplay measurements are created from this aggregate report.

## Upgrade test

Close the currently installed Hub. Extract the candidate and run its installer:

```fish
unzip -n ~/Downloads/NAnnersVRhub-0.5.1-rc1-source.zip -d ~/Downloads
and cd ~/Downloads/NAnnersVRhub-0.5.1-rc1
and python install.py
```

Open **NAnnersVRhub** from the application menu. Confirm **0.5.1-rc1**, all four
games and your saved tests. This must use the installed copy, rather than
`python -m vrhub.gui` from the download folder.

Close the Hub before switching versions. The source folder can be renamed or
moved after installation; older Steam-referenced guard folders still need to
stay available until their paths have been reviewed.

## Rollback and return

```fish
~/.local/bin/nannersvrhub-manage rollback
```

Open the application-menu entry again. Confirm **0.5.1-dev1**, the same four
games and saved tests. Close it, run the identical rollback command again and
reopen the menu entry. Confirm **0.5.1-rc1** and the same saved data.

The second command swaps back to the candidate; no reinstall is required. Stop
and share the exact error if a command fails. Rollback changes application
code/resources only and does not rewind test history, mod records or games.

## Validation and remaining acceptance

The candidate has the same 237 unit tests. Its extracted source and upgrade
patch are checked; isolated real-PySide6 tests exercise actual dev1 -> candidate
upgrade, candidate reinstall, rollback to dev1 and return to the candidate,
with existing data preserved. These are application-deployment fixtures, not
new VR gameplay tests. See INSTALL-VALIDATION-0.5.1-dev1.md for underlying
installer, wheel, desktop-parser and support-report coverage.

At candidate preparation, the upgrade/rollback/menu sequence above remained
pending. The acceptance update at the top records the subsequent user pass.
