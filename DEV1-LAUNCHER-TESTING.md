# NAnnersVRhub 0.5.5-dev1 — Launcher Foundation

**Status:** Desktop acceptance pending. Implemented on isolated development branch `dev/0.5.5-launcher-foundation`, based on verified component-update branch `dev/cyberpunk-component-updates`. Released 0.5.4 remains on `main` and was NOT modified.

## What's new

- Original-brand banana-yellow / charcoal / cyan launcher navigation.
- Sidebar containing **all nine existing recipe identities**, showing short game names and **detected/not detected** status. No fabricated VR-ready or headset-playability claims.
- Games and VR System navigation that switches the two pre-existing Hub pages rather than replacing scanning logic.
- Game title banner showing **actual** Steam/Heroic discovery, installed mod counts, and available mod-update count when checked.
- Visible quick actions: Launch game, Preflight, Refresh update status, Install mod file; and the existing DOOM KHARVOX folder selector when applicable.
- **More tools and advanced actions** disclosure retaining all existing mod management, profile, diagnostic and DOOM actions.
- **Show detailed library table** disclosure retaining the full original five-column table, selection behavior, and nine original row objects.
- Existing Setup guide, Compatibility profile, Controller bindings, VR System, support reports and development save tools remain reachable.
- Downloads, Backups, Settings and Logs **explicitly disabled as future navigation** to avoid promising unfinished actions.
- Banner uses the tested fallback display style: no remote/copyrighted artwork downloaded for Dev1.

## Not yet implemented

- Per-game hero artwork, dynamic game-page dashboards and game-card imagery (**Dev2**).
- Dedicated structured Mod updates tab beyond existing grouped read-only HTML (**Dev3**).
- Download destination setting, package manager, checksum/installer workflow (**Dev4**).
- Per-mod rollback, retained archives, save-safe restore points (**Dev5**).
- New live/VR success claims: only actual verified evidence is allowed.

## Validation performed

- Source Python syntax / import and 9 recipe checks.
- Existing GUI regression subset: 56 passing.
- New launcher-specific selection/navigation/branding/accessibility tests: 8 passing.
- Complete test suite: **612 passed, 1 skipped** (`QT_QPA_PLATFORM=offscreen`), before final non-functional scrollbar styling and preview label adjustment.
- Read-only real Qt preview verification: **14/14 checks passed** with live Nexus response, real GUI selection and screenshot capture. It used a **private copy** of state and kept the installer, game-launch and app-update buttons disabled.
- Old release and component-update branches remain intact.

## Desktop acceptance checklist

1. Read-only test window opens with **NAnnersVRhub 0.5.5-dev1 · PREVIEW** in the brand header.
2. Game library sidebar scrolls through all nine existing profiles. Selecting Cyberpunk, Fatekeeper or Valheim changes the main page title and setup guide.
3. **VR System** and **Games** navigation switches back and forth without losing the selected game.
4. **Show detailed library table** reveals the original five-column game list, if needed.
5. **More tools and advanced actions** reveals original controls (disabled in read-only preview).
6. Existing Setup guide, Compatibility profile and Controller bindings remain readable at typical desktop window sizes.
7. Black/charcoal, banana-yellow and blue branding look right. No bright white launcher scrollbars.
8. Read-only preview cannot install/uninstall mods, launch games or perform hub self-update.
9. Closing the preview does not close or modify the released hub.

## How the safe preview runs

The test harness is `tests/manual_launcher_dev1_preview.py`. It **requires** a private state copy via `VRHUB_STATE`, the existing Nexus API-key-file **path only**, and uses a separate XDG config/cache/data directory. Run `--verify` for an automated offscreen Qt test or `--desktop` for KDE human review. Do not point `VRHUB_STATE` at the production state file; the harness refuses that.

Do not run `install.py`, `nannersvrhub-manage install`, or the normal launcher to test Dev1. Do not switch the active OpenXR runtime, modify any game folder, or upgrade/uninstall mods during the launcher-layout acceptance step.

## Review notes

The approved full-width Cyberpunk game-page artwork mockup is a **multi-milestone design direction**, not a screenshot of 0.5.5-dev1. Dev1 is the navigation/architecture foundation only. The responsive art and mod table come after the shell is visually accepted.

## Dev1 follow-up: sidebar readability (November 20)

The user's first KDE screenshots confirmed all original controls and the updated launcher navigation worked, but the **left navigation text was too small**. In the same isolated Dev1 worktree we increased the game list to two-level typography: **15px semibold game titles** and **12px detection text**, using the existing yellow/green/charcoal palette. The list is now slightly wider with 65px rows and obvious selected/hover state. `Game detected` still means an installation was found, not VR gameplay success.

Sidebar header, navigation controls, future-section labels and helper copy were enlarged. To preserve space for the nine games, the disabled Downloads/Backups/Settings/Logs future buttons are now behind a collapsed **Future sections** disclosure. They remain disabled and clearly indicate forthcoming milestones.

Validation: **614 tests passed, 1 skipped** in Qt offscreen full suite; **14/14 automated GUI preview checks passed**, including live read-only Nexus data, navigation, action disabling, and screenshot capture. New tests cover font/row data, game selection and future-section expanding. A rendered screenshot was visually inspected; the wider game list and larger text were visible, without altering the existing brand colors.

**User acceptance of the revised KDE preview is still pending.** No game files, mods, saves, production state, released 0.5.4, or system runtime settings were changed.
