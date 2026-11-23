# Dev5D3-Y2 — Restore Read-Only VR System & Hide Unfinished Sidebar Pages

## Goal
Repair two player-facing defects reported in desktop-approved Y1: the VR System dashboard has been stuck on "checking" since the first preview, and the sidebar advertises unusable Downloads, Backups, Settings and Logs future pages. Restore useful system feedback without weakening preview protections or changing the installed stable app.

## Facts observed
- Approved parent Y1: commit 1091b23dbeef4f3007d5708d718de82336a4b2c8, clean when branched. Stable NAnnersVRhub 0.5.4 and prior checkpoints were not modified.
- The actual gui.HubWindow.scan_setup() uses an asynchronous ScanWorker that calls system_scan.scan() or refresh_live(). The scanner only inventories the host OpenXR runtime, library/loaders, adapters, Steam availability, WiVRn D-Bus status and process/socket indicators. It opens no XR session, installs nothing, does not start SteamVR/WiVRn and writes no user files. Copy report uses only the clipboard; Save report would write an explicitly selected file.
- Every historical GUI development preview, including Y1, monkeypatched gui.HubWindow.scan_setup to a no-op. This stopped the startup scan, manual Scan button, live refresh and report population, leaving the four VR status labels indefinitely on "checking". This is a *preview suppression*, not a fault in production's scanner.
- The preview uses an isolated XDG_CONFIG_HOME, which can hide the host's real OpenXR selected manifest. The original host runtime precedence honors XR_RUNTIME_JSON, and an existing host manifest may safely be referenced read-only without changing the user's runtime.
- The sidebar's four future pages are explicit disabled placeholders from LauncherSidebar, with no destination view; existing download, backup/recovery and log tools are elsewhere inside the game workflows. Historical tests referenced those widgets even though they had no behavior.
- Direct read-only host scan: HOST CHECKS PASSED; runtime manifest selected, no runtime server observed, headset/controller tracking unverified. During final isolated UI test, the current host manifest resolved to SteamVR. This is a point-in-time observation, not approval to change runtime or assert headset readiness.

## Proposed defaults / implementation
- Branch Y2 from approved Y1; do not edit the working preview or installed stable release in place.
- In the NEW Y2 preview, restore the **original gui.HubWindow.scan_setup** for --show. Keep the scan no-op in disposable --verify GUI layout tests only; independently test the original QThread scan behavior via a separate fixture-backed Qt unit suite and actual read-only host screenshot.
- Permit only read-only Scan my VR setup and Copy system report controls in the safety preview. Prevent arbitrary Save report writes and retain all original disabled real-game install, download, save-edit, recovery, self-update and modification actions. The installed production GUI remains unchanged.
- When using private XDG_CONFIG_HOME, set XR_RUNTIME_JSON only if the user's environment has not already set it, pointing to the current host's *existing* OpenXR selected manifest. Do not copy, rewrite, reselect or launch any runtime. Preserve explicit user override.
- Hide and disable the four future placeholder links and their toggle in normal LauncherSidebar. Retain the widget references as nonfunctional, invisible compatibility hooks for old preview safety allowlists and historical tests; never claim the planned pages have been implemented.
- Keep visible navigation as Games and VR System only. All existing game tabs, Downloads+optional folder scans, Updates, integrity and recovery controls remain in their existing locations. No new tabs or technical milestone planner.

## Decision needed
User reported these visible defects after passing Y1 acceptance. These two reversible fixes are implemented in isolated Y2. Manual Y2 desktop acceptance is pending. No live VR game, headset test, runtime switch, installation/recovery or self-updater authority has been granted.

## Scope
- vrhub/launcher_ui.py: hide and disable nonfunctional future navigation, including guarding the legacy _set_future_visible handler against unexpected programmatic expansion; keep existing game library and VR System nav and internal planned_buttons references.
- tests/manual_launcher_dev5d3y2_preview.py: new isolated Y2 preview. Restore read-only VR scan in --show, retain fixture-only --verify isolation, allow safe scan and copy, explicitly block Save report writes, and read the current host runtime manifest without touching user OpenXR settings. Inherit the approved Y1 development-tools fixture gate.
- tests/test_launcher_shell.py: update the old expectation from expandable disabled future navigation to genuinely hidden and non-clickable dead pages.
- tests/test_player_first_vr_dashboard_y2.py: real Qt ScanWorker startup, manual rescan, live refresh, clipboard reporting, safe preview mutation gates, invisible dead-sidebar controls and host-manifest read-only override precedence.

## Safety / rollback
- Separate worktree ~/Projects/NAnnersVRhub-0.5.5-dev5d3y2, branch dev/0.5.5-player-first-vr-system, parent Y1 commit 1091b23.
- No actual mods, game roots, Proton prefixes, headset runtime selection, installed Stable app, saved scans, custom archive preferences, backups, Nexus credentials, game saves, update records or ownership digests changed.
- Preview continues to share existing development-preview state only for the desktop show path; tests use disposable copies. The only intentionally enabled extra actions are read-only Scan and clipboard Copy.
- Real runtime selection might change independently after inspection. A selected runtime is not evidence that its server/headset/controllers are running. Do not activate, stop, repair or change it on user's behalf.
- Rollback source by returning to approved Y1 worktree/commit; never delete user saves or archived recovery records.

## Tests
- Focused Qt/system/launcher tests: 38/38 passing after separating immediate tab-switch live-refresh races from explicit user-triggered rescans.
- Full regression discovery: 1,488 tests run; 1,487 passed and one skipped; zero failures.
- Nine-game disposable KDE harness: 135/135 checks passed, including hidden dead sidebar, guarded install action and the prior Development Tools toggle/rehearsal checks. The 1280x720 Fatekeeper primary action remains in viewport.
- Actual isolated VR System UI screenshot at 1440x875: HOST CHECKS PASSED report is populated, runtime selected, manual Scan and Copy enabled, Save disabled in preview; future navigation not visible. Existing runtime observed as SteamVR on this scan; server not observed, headset/controllers unverified. No headset was connected or tested.
- Protected preview state, scan snapshot and custom folder preferences checked against prior SHA-256 baselines. Nexus credential is read-only/not copied.

## Desktop acceptance
1. Open Y2 preview. The left sidebar has real Games and VR System links, not Future sections / Downloads / Backups / Settings / Logs placeholders.
2. Open VR System: the runtime/server/headset status pills and report populate instead of staying "checking". Scan my VR setup can be pressed again and completes; Copy system report works. Save system report remains disabled **in the read-only safety preview**, intentionally.
3. Auto-refresh toggles on/off when VR System is selected, without starting a runtime or claiming controller tracking, and the host's selected OpenXR manifest is reported accurately.
4. Check the nine game profiles, the player-first install action before the ZIP list, archive scanning, and Updates and Advanced diagnostics still work.
5. Development tools remain optional; the fixture-only rehearsal does not appear unless explicitly enabled, and no live installer, game-recovery, save-edit or update button was newly enabled.
6. No layout overlap, unexpected dialog or modification to mod files, saved scans, backup data or runtime preferences.

## Deferred
Replacing placeholder pages with actual useful pages only when workflows are real; any changes to user's selected runtime, live server/headset connection or controller verification; real headset gameplay validation; live mod update execution and backup recovery authorization; public release.
