# Dev5E2 — Fatekeeper verified UEVR backend dependency

Parent approved Dev5E1 KDE acceptance: `83ad3cc29ce0d11401820d15264292e55e4d3888`
on `dev/0.5.5-fatekeeper-backend`.

## Goal and observed facts

Make the previously gameplay-confirmed joeyhodge `UEVRBackend.dll` visible as
a **separately tracked, read-only** dependency for Fatekeeper, while keeping
the existing two ZIP archives and current game installation/recovery gates.
The backend was previously verified during the two-archive review but not
shown independently in the Updates list.

Verified on the working install: `UEVRBackend.dll` in Fatekeeper's
`drive_c/uevr` folder is a regular 15,203,840-byte file whose SHA-256 is
`b883dd7f0b5e06bff74b42b4fabc66fc7c39c6baff57634d5132abe5b05ed6fc`.
The pin and approved source already exist in `uevr_dependency_review.py`:
`https://github.com/joeyhodge/UEVR/releases/tag/100526UE58_6RefreshUpdate`.
This exact build was confirmed during successful Quest 3 gameplay in FK7.
A file hash cannot establish in-process DLL loading, future compatibility,
installation ownership, or the latest upstream version.

## Implemented scope

- Added a standalone backend entry **UEVRBackend.dll (joeyhodge)**,
  dependency type **Backend**, to Fatekeeper's **existing Updates list**.
  It has one official source link and clearly identifies the pinned tested
  build; it does **not** become a third archive to scan or a false newer
  release alert.
- Status is derived on user-initiated update refresh from a safe read of
  the actual Proton-prefix DLL: **Verified pinned build** for exact
  size and SHA-256, **Not installed** when missing, **Review version**
  for wrong size/hash, unsafe symlink or unknown prefix. A missing game
  prefix does not misreport the backend as missing.
- The current pinned build is already preserved by the existing
  Fatekeeper archive review's Install/Replace/Preserve logic. No new
  installer or automatic replacement was added; divergent versions
  require manual compatibility review.
- Historical archive IDs and saved scans, recipe source pins,
  injector/profile staging, rollback journal and installation gate
  remain unchanged. Existing `UEVRBackend.dll` and `LuaVR.dll` are
  **not** written, downloaded or replaced by this milestone.
- The status is a **tested-build identity check**, never a claim that the
  newest joeyhodge release is compatible or installed.

## Safety and proof

Implementation uses a read-only file descriptor with `O_NOFOLLOW` and
`fstat` to refuse symlinks and nonregular files before hashing. The
resolver stays inside the game's Proton prefix. Tests use disposable
directories and patched pins; no real game files are used as test fixtures.

- Focused backend + dependency update + source tests: **18 passed**.
- Full unit test suite after adding ten backend cases: **1,526 run;
  1,525 passed, one skipped**.
- Live on-disk *read-only* verification: working Fatekeeper backend
  matches the source pin exactly.
- Stable 0.5.4, active Fatekeeper and Hogwarts profiles, Steam settings,
  Hub ownership records and the existing development preview untouched.

## Product fit

**Aligned — direct user value.** Fatekeeper players can tell whether
their backend matches the VR-tested build without interpreting a ZIP
contents listing. Two ZIP downloads remain two ZIP downloads. Existing
Updates and source-link controls suffice; no new tab or button.

## Desktop acceptance — player pending

- [ ] Previous Dev5E1 KDE preview PID `11318` identified and safely closed.
- [ ] Exactly one new Dev5E2 full KDE preview running from the recorded commit.
- [ ] Select Fatekeeper → **Updates**; see the separately named Backend
      dependency with **Verified pinned build** and official source link.
- [ ] Still see the two existing injector/profile dependencies; no third ZIP
      archive and no false backend update notification.
- [ ] Installed, missing, altered and symlink cases remain truthful in
      offline tests; real Fatekeeper installation and stable Hub unchanged.
- [ ] Live installation controls remain blocked; no new replacement action.
- [ ] Player explicitly accepts the interactive KDE experience.

## Deferred / not authorized

No backend upgrade policy, new release adoption, unattended backend
repair, real game mutation or release promotion is approved. Installed
matching bytes are treated as verified, not as a Hub-managed ownership
record. An actual backend version change requires separate compatibility
evidence, verified backups, rollback and user approval.

## KDE preview checkpoint — technical verification complete, player pending

2026-11-24 Pacific. Dev5E2 implementation checkpoint:
`972240723f1384fc87a2e3ed80218e93b428d76f`.
The older Dev5E1 preview PID `11318` (launched from the approved
`fe05f67` code) had a blocked, read-only Hogwarts profile review dialog
open. Both the dialog and then its parent preview were closed through
**normal KWin window-close requests**, after matching process PID, exact
window captions, parent worktree and closeability. No force termination
or production Hub action was used.

A first Dev5E2 GUI preview verified the new dependency, then an on-screen
review caught that the heading **Up to date** would imply latest-upstream
verification. A corrective commit changed the group heading to
**Verified pinned builds** and added a separate tested-build summary count.
Focused UI tests passed after the correction, followed by a repeated full
suite: **1,526 tests run, 1,525 passed, one skipped**.

The first Dev5E2 preview PID `15748` was normally closed; its successor is
**PID `16461`**, started from corrected implementation checkpoint
`9722407` with `python3 -m tests.manual_launcher_dev5e2_preview`.
A KWin window inventory confirmed **exactly one** development window with
caption `NAnnersVRhub Dev5E2 - Fatekeeper Backend Dependency`. Startup
reported `backend: verified`, using the installed DLL's SHA-256, while
archive roles remain two. The new preview stays open. Because another app
was in active use, the preview was **not forcibly focused**; review it
through KDE normally.

- [x] Previous approved preview safely identified and closed.
- [x] Exactly one current Dev5E2 interactive KDE window, PID `16461`.
- [x] Correct implementation Git commit; no unrelated worktree changes.
- [x] Backend status matches the current file; existing ZIP roles unchanged.
- [x] Stable installation, games, recovery data, and live-install gate preserved.
- [ ] Player confirms the revised screenshot/UI and accepts Dev5E2.

**Player check:** select Fatekeeper → Updates in the open preview.
Confirm the UEVRBackend.dll row is under **Verified pinned builds (1)**,
with Backend type and Open source, while `uevr.zip` and
`SLASHER-Win64-Shipping.zip` remain separate. The summary must say
**1 tested build verified** rather than **1 up to date**. No live backend
installation is enabled.
