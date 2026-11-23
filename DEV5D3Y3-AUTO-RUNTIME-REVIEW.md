# Dev5D3-Y3 — Automatic SteamVR/WiVRn Runtime Recognition

## Goal
Detect whichever OpenXR runtime the user selects for VR mod testing, including changes from SteamVR to WiVRn and back, without manually choosing a runtime in NAnnersVRhub and without modifying runtime settings or starting a server. Keep headset connection evidence honest and the player-first VR dashboard concise.

## Facts observed
- Approved parent: Dev5D3-Y2, commit `7b650f1dd2b110ac604b5c37d93cc9f3cfe2da6c`. It restored the original read-only VR System scanner and user-approved side navigation.
- The existing system_scan.scan() calls runtime.active_runtime(), which observes loader-precedence OpenXR manifests and identifies SteamVR or WiVRn from the manifest library or target. It does not choose or activate either.
- The existing five-second live refresh already calls system_scan.refresh_live(). That compares selected manifest path + library with the previous snapshot and performs a full read-only rescan on change.
- The host currently has an `active_runtime.json` symbolic link pointing to a SteamVR manifest. This was changed intentionally by the user to test a SteamVR VR mod. No files or targets are changed in Y3.
- SteamVR process names can indicate a server process is observed, but do not verify a connected headset. Connection telemetry through this scanner is supported for selected WiVRn only. Controller poses, graphics rendering and per-game compatibility remain unverified.
- Y2 development-preview scan reports still use stable `0.5.4` version metadata, despite being a development preview.

## Proposed defaults
- Make runtime selection changes explicit and responsive: track the resolved manifest target as well as the path/library; if either changes, rebuild the read-only runtime and headset snapshot. Do not require restarting the Hub.
- Separate **OpenXR selected runtime**, **observed runtime server process**, **available headset telemetry**, and **unverified controller tracking**. For SteamVR, explicitly describe the lack of headset telemetry rather than implying WiVRn connection checks are relevant or that an unknown headset is disconnected.
- Keep the dashboard summary player-facing: OpenXR: SteamVR selected / WiVRn selected, and the last read-only live sample time. Preserve the original 5-second auto-refresh toggle and manual Scan action.
- Mark the development preview's exported report with `0.5.5-dev5D3y3` instead of implying the stable installed 0.5.4 app was changed.
- Never manipulate host OpenXR manifests, symlinks, runtime services, SteamVR/WiVRn processes, XR sessions, game installs, backups, or saved files.

## Decision needed
The user asked for automatic SteamVR/WiVRn recognition after approving Y2. The narrow read-only feature is implemented in a separate worktree. Real KDE desktop acceptance remains pending; neither server/headset presence nor gameplay has been verified by these tests.

## Scope
- `vrhub/system_scan.py`: add safe resolved-target comparison to the existing automatic live selection refresh, dynamic runtime-specific report scope and SteamVR-specific "headset telemetry unavailable" explanation. Still read-only.
- `vrhub/gui.py`: show the current selected OpenXR runtime in the concise dashboard summary while preserving selected-vs-server-vs-headset status labels.
- `tests/test_auto_runtime_detection_y3.py`: isolated fake OpenXR manifest switches SteamVR → WiVRn → SteamVR, including symlink-target changes with unchanged library, disappearance, WiVRn D-Bus gating, no process launches/file mutation, and Qt status labels.
- `tests/manual_launcher_dev5d3y3_preview.py`: inherits all Y2 nine-game desktop checks and preview safety boundaries; adds simulated selected-runtime display checks and development report version tag.

## Safety and rollback
- Branch `dev/0.5.5-auto-runtime-detection`; worktree `~/Projects/NAnnersVRhub-0.5.5-dev5d3y3`, forked from approved Y2. Approved Y2 and previous historical checkpoints unchanged.
- All test runtime switch operations are on *invented manifests and symlinks inside temporary fixture directories*. The real host's OpenXR manifest and game installs are only read.
- The existing preview-only scanner may read process names through `/proc`, but must not start runtimes or open XR sessions. A standalone off-screen screenshot attempt encountered a long `/proc/<pid>` stat call in the inherited process inventory; that test never produced a new screenshot. The existing Y2 desktop scanner had been verified by the user; this Y3 behavior still requires user desktop acceptance. The process inventory was not rewritten as part of Y3.
- Save-report disk writes, installers, transfer actions and game modifications remain disabled in preview. Preserve Nexus key and per-game mod records, custom folders, backup history and saved scans. Source rollback is the unchanged Y2 worktree/commit.

## Tests
- Focused runtime/SysScan/VR dashboard suite: 34/34 passed.
- Full Hub suite: **1,494 run; 1,493 passed, one skipped**; no failures.
- Disposable nine-game KDE harness: **140/140** passed; explicitly checked SteamVR and WiVRn dashboard summaries, correct lack of cross-runtime headset telemetry, development preview version label, existing context-sensitive installation actions and development-tools isolation.
- User's actual headset/controller/gameplay state and an interactive SteamVR↔WiVRn change have not been tested. A headless real-process screenshot stalled during the old process inventory; do not claim that screenshot succeeded.

## Desktop acceptance
1. Open Dev5D3-Y3. With SteamVR selected, VR System shows SteamVR selected and separately reports whether the SteamVR server process is observed. Headset status should be Unknown, not Disconnected, if SteamVR telemetry is unavailable.
2. Press Scan my VR setup, then Copy report. The report should identify `0.5.5-dev5D3y3` and state SteamVR server-process observations vs headset telemetry limits accurately.
3. When convenient and safe, switch the host OpenXR selection to WiVRn using the user's own runtime manager. The dashboard should automatically recognize WiVRn on a subsequent live refresh or manual scan, without restarting the Hub. Confirm WiVRn connection telemetry when available; controllers remain unverified absent a real VR input test.
4. Switching the host selection back to SteamVR should update the dashboard and clear any stale WiVRn headset connection result. The Hub must not switch the runtime for the user.
5. Existing game scanning, Updates, contextual installation actions, safe recovery, optional development tools and clean sidebar remain intact.

## Deferred
Authenticated live SteamVR headset/controller telemetry, actual headset runtime session verification, game-specific Steam/Proton runtime overrides (a launched game can use a different runtime from the host selection), reliable cross-runtime game readiness verification, and separately approved real VR tests.
