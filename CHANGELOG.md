## 0.5.3

- Accept the October 21 rc1 gameplay report: bridge import/test/launch,
  rendering, tracking, controller input and stereo depth passed, with local
  configuration checks also passed.
- Finalize the stable Hub version and dated compatibility reference. Retain
  the exact accepted bridge 0.2.0 artifact and all runtime behavior.
- Keep publication and the real stable-endpoint update as explicit remaining
  release steps. Local historical test records are not rewritten.

## 0.5.3-rc1 — public release preparation

- Separate the full bridge component into its own pinned 0.2.0 source release;
  keep the Hub source ZIP compatible with published 0.5.2 update limits.
- Install the component only on explicit DOOM installation. Allow offline
  bridge import; verify archive size/hash, paths and all payload hashes before
  activating it. Other profiles load without the optional component.
- Preserve the tested lab engine/runner, local history and rollback behavior.
- Validate the actual 0.5.2 updater against a synthetic stable candidate.
- Prepare bridge 0.2.0 and Hub 0.5.3 release notes. Public publishing is pending
  the RC check and the connected tool's repository/release creation capability.

## 0.5.3-dev10 — standalone bridge and automatic runner installation

- Share the standalone NAnners KHARVOX Bridge 0.2.0-dev1 installer with the Hub.
- Install VR runner reuses a validated isolated runner or obtains the exact supported upstream base; source file hashes must match before patching a separate copy.
- Use one process lock across the new Hub and standalone actions. Keep the lab 0.1.6 engine and payload unchanged.
- Add bounded downloads/extraction, offline archive support and a standalone owned-runner uninstall that preserves games, prefixes, saves and logs.
- Record the user's successful October 21 dev9 Hub test including stereo depth, separately from the earlier 40-minute standalone test. Local histories are not rewritten.
- Preserve all nine profiles. Publishing and additional platform/game-store support remain pending.

## 0.5.3-dev9 — DOOM VR tested-runner integration

- Add Prepare VR runner and Test VR bridge actions to the DOOM profile; launch through the unchanged lab 0.1.6 engine after its matching full pass.
- Reuse existing standalone runner and result state. Verify bundled files, source runner pins, module hashes and the fresh-result identity before launch.
- Include full bridge binaries, licenses and corresponding source in source, wheel and managed installations. Reject incomplete packages before activation.
- Add launch/probe diagnostics and SFS state-lookup recognition. Keep historical logs separate from gameplay evidence.
- Record the October 21 user-reported 40-minute DOOM VR session with head tracking and both controllers. Individual mappings and stereo depth remain unconfirmed.
- Keep all nine game profiles and existing local test histories. The flat DOOM route stays with Heroic.
- Raise bounded update archive/per-file limits to carry the bundled source. Older installed versions require this build's included installer; they cannot safely install this larger preview through their older in-app updater.

## 0.5.3-dev8 — DOOM GOG/Heroic + KHARVOX 1.4 retest

- Restore DOOM as a ninth experimental guided profile using KHARVOX 1.4's GOG adapter and the supported Vulkan executable. Add a sourced Quest/Touch controller reference without claiming a Linux gameplay pass.
- Add an explicit external-package folder selector, 112-file inventory, eight pinned binary hashes, launcher/runtime PE version checks and the documented GOG executable digest. Keep the mod external and bundle no third-party binaries.
- Launch through umu-run using native Heroic's saved Proton/prefix, isolate inherited Steam IDs/prefix settings, pass runtime import and WiVRn IPC visibility, and retain bounded launch output. The flat fallback remains owned by Heroic independently of VR readiness.
- Add prefix log discovery and GOG CVar/layer failure diagnostics. Correct the old prototype interpretation of nativeAttempt=False: this is a retired Native-renderer flag, not proof that SFS/AER failed.
- Keep Elden Ring's unsupported-version launch check, prior eight profiles, existing install inventories, settings, saves and test histories.

## 0.5.3-dev7 — Elden Ring reinstall fix

- Allow installation into the empty Game/ERVR directory left by Uninstall mod, including a directory containing only the regular ERVR.log file. Preserve that historical log through reinstall and removal.
- Continue blocking foreign ERVR payloads/settings, unknown files/directories, symlinks, case collisions and other loader conflicts. Change no package pins, launch behavior, existing histories or game saves.
- Cover install → uninstall → reinstall with both empty and log-only residue, alongside the existing conflict and transaction tests.

## 0.5.3-dev6 — Elden Ring experimental profile

- Add Steam Elden Ring with the inspected ERVR 0.4.0 archive, pinned SHA-256 and complete ten-file installation under Game. Normalize its Windows ZIP separators with the existing transactional backup/removal engine; preserve the seven older recipes and inventories.
- Reject known conflicting VR loaders, unsafe archive paths and changed installed binaries. Read executable PE version metadata without loading the game; require the documented 2.6.2.0 or 2.7.1.0 builds for launch.
- Add an executable adapter for copied Steam launch options that substitutes eldenring.exe and retains the selected Proton/prefix. Unknown commands, missing adapter code or unsupported builds stop launch. Steam/game offline settings remain manual prerequisites; anti-cheat files are not changed.
- Add a sourced controller guide, saved ERVR configuration checks and ERVR/ReShade log discovery. Mark Linux/WiVRn gameplay unverified and document intentional cinema menus/loading. Bundle no mod binaries and create no gameplay success records.

## 0.5.3-dev5 — Reviewed controller-guide corrections

- Correct the Fatekeeper overlay conflict combination from L2 + L3 to L2 + R3; retain Insert as the recommended shortcut on this setup.
- Replace Skyrim MGO’s VRIK example with the user-reviewed Vanilla Quest / Touch layout: A activates, right grip shouts, left grip readies/sheathes, L3 sprints, and X opens the tween menu.
- State the confirmed exception explicitly: neither trigger readies sheathed weapons; normal trigger combat/casting and power attacks remain once readied. Preserve menu trigger input and Vanilla right-stick item zoom.
- These are reference-guide edits. They do not change installed bindings, mod settings, local test history or saves.

## 0.5.3-dev4 — Controller references

- Add Games → Controller bindings for all seven recipes with a local Quest / Touch button-location diagram, search, section filters and full-guide clipboard export.
- Link control rows to author references and distinguish user reports from documented defaults and preset-dependent mappings. Keep uncertain combinations unconfirmed.
- Include Subnautica stock Y/PDA and tested A-drag quick slots, UEVR overlay behavior, Hogwarts spell gestures, Cyberpunk context changes and VHVR building combinations.
- Record the October 20 user-reported Valheim pass (at least 30 minutes); leave piece rotation unconfirmed. Clarify that per-game Steam Linux Runtime overrides global Proton preference.
- Package all seven offline guides in source, wheel and managed installs, validate their inventory, and preserve prior test history and game data.

# NAnnersVRhub 0.5.3-dev3

- Adds Steam Valheim's Windows/Proton workflow with pinned VHVR 0.11.2 and BepInExPack Valheim 5.4.2351. Installs the complete VR payload, strips the loader wrapper and maps Valheim_Data to valheim_Data for Linux.
- Reuses the transactional BepInEx installer for Valheim and Subnautica, preserving old Subnautica inventories/backups. Keeps both games' package pins, validation and rollback separate; unrelated mods, settings, worlds/characters and local histories remain outside their installation targets.
- Supplies explicit VHVR VR-mode/motion-control command-line options and Direct3D 11/WiVRn/xrizer guidance without editing Steam or VHVR settings. Documents the upstream game-version range and SteamVR-process auto-mode limitation.
- Adds Valheim archive inspection, verification, compatibility checks, BepInEx log discovery and gameplay recording. Seven-game managed upgrades/rollback retain earlier data. Valheim gameplay remains unverified; no third-party binaries are bundled.

# NAnnersVRhub 0.5.3-dev2

- Records the October 19 dev1 user-reported Subnautica core VR SUCCESS, with October 20 stock-control follow-ups. Keeps the local historical FAILURE and SUCCESS records untouched.
- Makes Steam's Launch Subnautica in Steam VR Mode choice explicit. Documents stock Y/PDA and hold-A-and-drag quick-slot use, plus working A/trigger interaction on the tested setup.
- Documents the stuck in-game binding editor and unsuccessful Y/UIAssign test. Keeps stock bindings as preferred; installs no custom binding overrides and does not change game files during a Hub upgrade.
- Changes bundled evidence and guidance only. Configuration checks remain separate from dated gameplay evidence; longer sessions and other setups remain unverified.

# NAnnersVRhub 0.5.3-dev1

- Adds Steam Subnautica with SubmersedVR 0.2.1 and Tobey's BepInEx pack 5.4.23-pack.3.1.1. Pins the inspected author ZIP hashes and installs both Windows payloads together, preserving case and complete controller bindings.
- Backs up replaced files and retires the obsolete Tobey patcher directory. Failed installs/removals restore the previous file state; removal restores originals, saves changed settings in the backup, and stops for review when binaries changed.
- Adds WiVRn/xrizer Steam launch guidance, package inventories, archive inspection, compatibility checks, BepInEx log discovery and local gameplay recording. Does not bundle third-party mods, edit Steam options or claim a local Subnautica gameplay pass.
- Keeps all five existing recipes and existing user data. Managed deployment supports the new six-recipe inventory and rollback to 0.5.2.

# NAnnersVRhub 0.5.2

- Adds stable Hub update checks, optional automatic source downloads, verified in-app installation, explicit restart and managed rollback. Stable official GitHub releases only; installation remains an explicit action.
- Adds Hogwarts Legacy for Heroic/Epic with the matching HL_UEVR v2.0.6 injector/profile pair, complete script/plugin/model installation, backups, inventories, log diagnostics and local gameplay tests.
- Adds one-click UEVR injector launch using native Heroic's selected runner and prefix, with the manual Heroic route retained for Flatpak and unsupported setups.
- Records the October 19 dev4 user-reported one-click launch and VR rendering/tracking/controller/stereo success, plus short-session spell drawing and wrist-flick activation. Voice, body tracking, other gestures and longer sessions remain unverified.
- Keeps existing game installs, mod state, saves, backups and gameplay history in place. Runtime behavior is unchanged from accepted dev4; this promotion updates version labels, bundled evidence and release documentation.

# NAnnersVRhub 0.5.2-dev4

- Hogwarts Legacy: Run UEVR injector now launches the installed injector with native Heroic's saved Wine/Proton runner and existing prefix, without selecting the EXE each time. Proton uses the installed umu launcher when enabled/available, or its established compatdata layout; it never uses a game-launch URI for the secondary executable.
- Keeps the manual Heroic Run EXE on prefix guide for Flatpak, unsupported layouts and launch failures. Reports early exit codes and a bounded output tail; repeated clicks reuse a still-running launcher within this Hub process.
- Pins the selected Proton build and prevents inherited Steam prefix/ID settings from redirecting the injector. Does not install runners, rewrite Heroic settings, stop the game or auto-inject.
- Bundles the October 19 user-reported Hogwarts rendering/tracking/controller/stereo success using the manual Heroic route. Preserves historical local test snapshots. The new one-click route and optional body/gesture/voice features need separate live tests.

# NAnnersVRhub 0.5.2-dev3

- Correct Hogwarts Legacy to the user's Heroic/Epic storefront. Discover the
  Epic identity, game directory and selected prefix/runner from read-only Heroic
  metadata, supporting native and Flatpak configuration roots.
- Install UEVR/profile files into that prefix, resolving direct and nested pfx
  layouts and existing Windows AppData users. Reject ambiguous/missing installs,
  users and out-of-prefix destinations; do not substitute a Steam prefix.
- Add UEVR via Heroic guidance with copyable injector path and matching Heroic
  client opening. Heroic's Run EXE on prefix owns injection launch; the Hub does
  not rebuild its environment or invoke Steam protontricks for this game.
- Route game launch through Heroic/Epic and keep compatibility, profile inventories
  and log paths tied to the selected prefix. Preserve the original four Steam
  workflows, Hub updates, saved records and Heroic configuration.
- Test discovery, prefix/user layouts, metadata failures, isolation, GUI controls
  and the actual author archives. Hogwarts gameplay remains unverified.

# NAnnersVRhub 0.5.2-dev2

- Add Hogwarts Legacy's Steam/WiVRn UEVR workflow using the maintainer's packaged
  HL_UEVR v2.0.6 injector and complete HogwartsLegacy profile.
- Add prefix-specific install/profile inventories, backend/script/plugin checks,
  expected per-game UEVR log diagnostics and unverified gameplay evidence.
- Preserve the existing four recipes and Hub update controls. Do not bundle mod
  archives, change game settings or invent a successful Hogwarts gameplay test.
- Declare packaged recipe requirements per release, probe each release's own
  inventory, and preserve the current independent manager across app rollback.
  This supports returning between four-game and five-game releases.

# NAnnersVRhub 0.5.2-dev1

- Add a separate Hub updates screen for official stable GitHub releases, daily
  startup checks, optional automatic downloads, progress and cancellation.
- Verify published checksums/digests, bounded archive contents and version/resource
  completeness without importing downloaded code. Recheck cached contents before
  explicit installation; reject older releases and source-mode activation.
- Reuse managed installation, dependency checks, atomic activation and rollback.
  Keep the running process pinned until explicit restart. Reject stale activation
  if another window changed the installed version.
- Preserve game files, runtime selection, mod inventories and saved gameplay tests.
  Store updater preferences and downloaded archives separately.
- Add network-failure, unsafe-archive, cache-tampering and real Qt/managed-upgrade
  checks. Desktop/network acceptance is still required; no new gameplay evidence
  is claimed.

# NAnnersVRhub 0.5.1

- Promote the accepted installer candidate to final with unchanged installer,
  guard, recipe and game behavior; runtime changes are limited to the version label.
- Record user-reported independent startup, four games listed and two unspecified
  games working, followed by aggregate acceptance of upgrade/rollback/return.
- Prepare source installation, desktop shortcut, local upgrades, app rollback and
  complete runtime resource packaging for GitHub release.

# NAnnersVRhub 0.5.1-rc1

- Record user-reported dev1 acceptance: independent installed startup, all four games listed and two unspecified games running as expected.
- Prepare a version-label-only candidate for real desktop upgrade/rollback acceptance; keep installer, guard, resources and game workflows unchanged.
- Keep GitHub publication on hold pending the candidate checks.

# NAnnersVRhub 0.5.1-dev1

- Add an offline per-user installer with dependency/resource checks, permanent
  versioned app copies, stable launchers and an application-menu entry.
- Add explicit local source upgrades, status and integrity-checked rollback;
  preserve existing gameplay history, mod records, backups and game settings.
- Package all four recipes inside vrhub, including them in regular wheels;
  provide installed guard/management entry points and stable managed guard paths.
- Keep GitHub publication on hold pending desktop installer acceptance.

# NAnnersVRhub 0.5.0

- Promoted the accepted RC1 source build to final 0.5.0, preserving the frozen dev8 runtime behavior and existing four recipes.
- Recorded the October 18 desktop startup/history confirmation and the user's aggregate Pass response to the RC1 gameplay smoke-test request. Earlier detailed gameplay records and known menu/overlay limitations remain separately dated.
- Updated release/upgrade documentation and final source packaging. Runtime changes from RC1 are limited to the version label.

# NAnnersVRhub 0.5.0-rc1

- Froze the dev8 feature set for release-candidate desktop acceptance. Runtime changes are limited to the displayed/package version; launch/install/profile, runtime selection, reports and recipes retain dev8 behavior.
- Added the 0.5.0 release notes and final candidate checklist, with automated validation, user-reported gameplay evidence and pending desktop checks kept separate.
- Clarified the supported extracted-source/editable distribution path and the stable-folder requirement for existing Steam guard paths. This candidate does not ship a standalone non-editable wheel/system package.

# NAnnersVRhub 0.5.0-dev8

- Changed readable/interface scan, compatibility, history and support timestamps to 24-hour system-local time with timezone labels. Stored JSON timestamps and recorded history are untouched; date-only references and literal log excerpts retain their original meaning.
- Added a persistent captured-snapshot time/age panel, renamed the recollection action to Collect new snapshot, and made the effective export format, excerpt inclusion and home-path replacement visible. Copy/Save still export the captured evidence; only explicit recollection reads sources again.
- Added per-finding last-occurrence metadata from the last matching line in the bounded tail. Timezone-less/missing log timestamps are never guessed or replaced with file modification time. Metadata remains when excerpts are omitted, without declaring errors active/resolved.
- Added local-time report filenames with an explicit no-excerpts suffix when appropriate, plus a troubleshooting guide and release-candidate desktop checklist.
- Added 17 regression tests for local time/DST/day rollover, unknown zones, snapshot age, report/JSON immutability and last-occurrence scope. Existing game launch/install/profile behavior remains unchanged.

# NAnnersVRhub 0.5.0-dev7

- Added Create support report in the Compatibility profile view: fresh background collection, literal text/JSON preview, copy and save for the selected game.
- Combined the host scan, current compatibility/configuration checks, bounded log findings, and latest explicit local gameplay test with its historical setup snapshot. Preserved each section's dates and evidence scope. Missing sources remain visible; exceptions produce a usable partial report.
- Added optional Linux-home-prefix replacement (on by default) and log-excerpt omission. Copy/save use the same prepared content as the preview. Saved files are private, atomic new files; existing files are never overwritten. Collection performs no upload or gameplay-history write.
- Added `support-report GAME [--json] [--output NEW_FILE] [--file LOG ...] [--no-excerpts] [--include-home-path]` and independent support-report JSON schema version 1.
- Recorded Fatekeeper's October 18 user-confirmed workaround in its profile: 2D Screen Mode off, close the in-game UEVR overlay using Insert, and avoid the controller shortcut that also opens WayVR during this test. No launch, injector, runtime, Proton or in-game-setting changes are made.

# NAnnersVRhub 0.5.0-dev6-fix1

- Fixed a demonstrated diagnostics gap: the user-supplied Fatekeeper log had repeated `xrEndFrame ... XR_ERROR_VALIDATION_FAILURE` in the inspected tail, but dev6 reported no known signatures. Added symbolic and contextual numeric (-1) recognition.
- Added informational recognition of `xrBeginFrame ... XR_FRAME_DISCARDED` (+9). The application's error-level label is preserved as evidence, while the finding explains its OpenXR success-status semantics.
- Added four regression tests, including an anonymized bounded-tail reproduction and unchanged UEVR config/history checks. No launch, mod installation, runtime, Proton, frame-timing or game-setting changes are included. The rendering failure remains under investigation.

# NAnnersVRhub 0.5.0-dev6

- Added a background, read-only Game log diagnostics dialog with expected-path scans, explicit selection, refresh and copy.
- Added `logs GAME [--file PATH ...] [--json]`; automatic paths cover CyberpunkVR Port and Fatekeeper's expected per-game UEVR log. Other games support explicit log selection.
- Recognizes OpenXR invalid-pose, unavailable-runtime, missing-extension and missing-graphics-requirements signatures. Cyberpunk's invalid-pose finding includes the previously tested panel workaround and the October 18 report of menu passthrough returning to full VR on exit. Menu depth-gate messages remain informational; no root cause or permanent fix is claimed.
- Shows file modification time/age, stale/future timestamps, bounded occurrence counts and excerpts. Missing/empty/unreadable logs and unrecognized signatures stay unverified. Compatibility status and gameplay history are unchanged.
- Added bounded file/tail/line handling, binary/special-file/symlink rejection, and tests for evidence scope, stale logs, false positives, malformed input and non-mutating scans.

# NAnnersVRhub 0.5.0-dev5

- Added Record live test and Test history in the Compatibility profile view.
- Local records store explicit outcomes, per-area Passed/Failed/Not Tested results, notes, local/UTC recording timestamps, and historical configuration findings/workaround metadata.
- Added prominent latest-local-result reporting, history selection/copying, CLI record-test/test-history and additive compatibility JSON fields.
- Kept local gameplay reports separate from automatic readiness and bundled references; historical success does not hide a newer local failure or remove Cyberpunk's workaround.
- Added separate private, append-only local history with serialized atomic saves and non-destructive handling of malformed history; no installer bookkeeping or game settings are changed.
- Added matching dark styles for recording/history dialogs and explicit form validation without additional confirmation prompts.
- Validation: 146 tests plus Qt cancel/validation/save/history/copy/later-failure/restart checks pass; report and recording-dialog visuals inspected. User desktop validation remains next.

# NAnnersVRhub 0.5.0-dev4-fix2

- Added Ready or Not's October 17 user-reported live-test reference.
- Recorded Cyberpunk's successful immersive-rendering test with required panel-disabling conditions; retained its experimental classification and explicit untested stereo-depth/stability/HUD-restoration limits.
- Added validated user-reported-workaround evidence with a mandatory dated reference and non-empty workaround instructions, displayed prominently in text and GUI reports.
- Recorded the observed xrEndFrame res=-39 and panel-dependent symptoms without claiming the exact underlying fault is proven.
- Validation: 124 unit tests and GUI evidence/workaround/clipboard checks pass. No game/mod settings, launch or install behavior changed.

# NAnnersVRhub 0.5.0-dev4-fix1

- Recorded the user's successful October 17 Fatekeeper live test as a dated, user-reported reference.
- Fatekeeper's gameplay label now reads USER-REPORTED LIVE TEST; current local checks and manual-review status remain independent.
- Captured the recorded proton-cachyos-slr runner name and file counts from the submitted report without inventing an exact Proton version or automatic telemetry.
- Validation: the existing 122-test suite passes with updated evidence expectations; GUI evidence/clipboard checks pass. No launch or install behavior changed.

# NAnnersVRhub 0.5.0-dev4

- Added compatibility profiles for Cyberpunk 2077, Fatekeeper and Ready or Not, covering their existing recipe workflows.
- Added separate gameplay-evidence labels; Cyberpunk remains experimental, Fatekeeper/Ready or Not have no dated gameplay reference, and Skyrim records the user's successful October 17 dev3-fix1 launch/controller test.
- Added declarative read-only file/tool/inventory checks and recorded Proton discovery without guessing a different installed runner.
- Cyberpunk compatibility requires the phase-2 VR port in addition to base-game dependencies. Existing base-game launch-guard semantics are retained.
- Fatekeeper checks injector/backend/profile config and recorded install/profile files; Ready or Not checks recorded VRO PAK files under the current installation.
- Inventories detect missing files, wrong roots/types, and symlinks escaping the expected install. Untracked/manual installations remain incomplete rather than being inferred from arbitrary files.
- Manual-review rows identify settings that are not automatically inspected. File checks do not promote gameplay evidence or force settings/Proton/mod changes.
- Validation: 122 unit tests and Qt all-profile/evidence/clipboard/stale-file/tab/close smoke checks pass. Live testing of the new profiles remains with the user.

# NAnnersVRhub 0.5.0-dev3-fix1

- Corrected the active-profile OpenComposite check to accept the user's enabled Unleashed variant, including numeric version suffixes, while retaining the legacy XR variant.
- Preflight inventories both recognized adapter variants; compatibility requires the enabled variant's own directory and reports multiple enabled variants.
- Added the actual FSR/DLAA and CAS/Default VR Performance Kit names to conflict detection.
- Shared active-profile parsing between preflight and compatibility; confirmed disabled conflict folders no longer produce a review notice.
- Updated guidance to avoid requiring the disabled legacy XR mod. The October 17 configuration snapshot is recorded separately from the October 6 gameplay reference.
- Validation: 97 unit tests, GUI Unleashed/copy/conflict-transition smoke checks, and three patch-baseline reproductions pass. Live fix1 testing remains with the user.

# NAnnersVRhub 0.5.0-dev3

- Added a Compatibility profile view inside Games, with refresh and copyable reports.
- Added optional validated compatibility metadata and dated gameplay references, separate from installable UEVR profiles.
- Documented the first profile for Skyrim VR/MGO using the user's October 6 CachyOS/WiVRn/Quest 3 gameplay and dev2 reconnect results.
- Compare local runtime/library, MO2 shortcut prefix/recorded Proton, simple runtime-import launch assignments, and active-profile enabled mods with the documented workflow.
- Enabled OpenComposite and VR Performance Kit conflicts are evaluated from modlist.txt; missing, custom-root or ambiguous profile evidence stays unverified.
- Added text/JSON `compatibility` CLI reports and compatibility findings in Copy diagnostics.
- Existing launch/install guards and four game workflows are retained; the remaining games explicitly show that their compatibility profiles are not documented yet.
- Validation: 89 unit tests and Qt offscreen selection/refresh/copy/stale-evidence/tab/close smoke checks pass. Dev3 live headset/gameplay testing remains with the user.
- User validation of dev2: connected -> unknown -> connected recovered WiVRn and host status correctly on CachyOS/WiVRn/Quest 3.

# NAnnersVRhub 0.5.0-dev2

- Added read-only WiVRn `HeadsetConnected` telemetry and optional connected-headset `SystemName` through the user session bus.
- Added separate dashboard states for runtime selected, server running, headset connected/disconnected/unknown, and controllers unverified.
- Added background live-status refresh every five seconds while the VR System tab is open, with a pause checkbox, separate host/live timestamps, and no overlapping poll workers.
- Unavailable/malformed/timed-out telemetry becomes UNKNOWN and clears prior connection evidence; connection does not certify controller tracking or rendering.
- Uses bounded explicit D-Bus Properties.Get calls with automatic startup and interactive authorization disabled; never starts WiVRn, opens XR, changes configuration, or reads pairing secrets.
- Fixed custom xrizer/OpenComposite inventory reporting, including configured `/opt/xrizer` paths, and normalized runtime library file paths.
- Prioritizes the runtime library identity over misleading manifest directory names when identifying runtime selection.
- JSON scan schema version 2 includes separate live connection evidence; host-only CLI exit semantics remain unchanged.
- Validation: 67 unit tests pass; Qt offscreen automatic transition/copy/export/tab/worker-lifecycle smoke checks pass using telemetry fixtures. Live WiVRn/Quest connection changes remain to be validated on the user's system.
- User validation of dev1: CachyOS/WiVRn host scan and Skyrim VR/MGO preflight passed; Skyrim VR launched normally with both controllers working.

# NAnnersVRhub 0.5.0-dev1

- Added the **VR System Dashboard** and a separate **Games** tab while preserving the four existing game workflows.
- Added **SCAN MY VR SETUP**, a read-only background host inventory, plus copy/save text reports.
- Added `python -m vrhub.cli scan` and `scan --json` with a versioned JSON report.
- Inventories OpenXR selection/library, host loaders, runtime server processes, compositor sockets, host OpenVR adapters, Steam, and integration tools.
- Fixed runtime discovery to honor architecture-specific/XDG precedence and report invalid explicit overrides instead of silently falling back. Invalid runtime manifests no longer pass generic OpenXR preflight.
- Separates host file checks from actual headset connection, controller tracking, game readiness, and graphics rendering; dev1 always marks hardware unverified.
- Added regression tests for precedence, malformed/unreadable manifests, missing libraries/loaders, adapter override precedence, process inspection, read-only behavior, report escaping, and CLI JSON output.
- Validation: 52 unit tests pass; Qt offscreen dashboard/background scan/copy/tab smoke check passes. Live CachyOS/WiVRn/Quest validation remains on the test machine.

# NAnnersVRhub 0.4.0

- Release-candidate cleanup pass.
- Removed the experimental **DOOM (2016) — GOG / Heroic + KHARVOX** recipe from the public game list because actual DOOM gameplay did not enter VR on the tested GOG/Proton/WiVRn path.
- Kept the generic Heroic/GOG handler infrastructure and KHARVOX diagnostic code in the source tree as development groundwork, but no unsupported DOOM VR workflow is exposed to users.
- Public supported workflow list is now intentionally limited to **Cyberpunk 2077, Fatekeeper, Ready or Not, and Skyrim VR / MGO**.
- Added a regression check that the packaged public recipe set contains exactly those four verified workflows.

# NAnnersVRhub 0.4.0-dev12

- Fixed KHARVOX discovery so versioned/wrapped folders such as `KHARVOX-v1.11` are preferred and detected without renaming.
- Added KHARVOX runtime diagnostics based on the Heroic prefix: VR-intro log, launcher log, native-stereo log, `nativeAttempt=False`, and Wine Vulkan registration state.
- DOOM Preflight now distinguishes **VR intro working** from **native stereo actually loaded** instead of treating the launcher as proof of game VR.
- Added an **Open KHARVOX log** action for the DOOM workflow.
- Sanitized stale troubleshooting overrides before starting KHARVOX: the Hub removes only the forced `VK_LAYER_KHARVOX_OPENXR` host-layer request while preserving unrelated Vulkan layers.
- NAnnersVRhub no longer tries to force KHARVOX's Windows `KharvoxLayer.dll` into Pressure Vessel's Linux Vulkan layer chain; loader debugging proved that the host loader cannot resolve that Windows layer.
- The tested GOG/Proton path remains explicitly experimental: KHARVOX VR intro and DOOM Vulkan launch work, but KHARVOX reports `nativeAttempt=False`, rewrites its implicit-layer registration to disabled, and does not create `KHARVOX-NATIVE-STEREO.log`.
- Normal **Launch DOOM** through Heroic remains unchanged.
- Added regression coverage for versioned KHARVOX discovery, host Vulkan environment cleanup, prefix diagnostic parsing, and native-stereo evidence. **35 tests pass.**

# NAnnersVRhub 0.4.0-dev11

- Added experimental KHARVOX detection for DOOM (2016) GOG/Heroic.
- Added **Launch DOOM VR**, which starts `KharvoxLauncher.exe` through `umu-run` while reusing Heroic's configured DOOM Wine prefix and Proton-CachyOS runner.
- KHARVOX remains external to the DOOM install; the Hub searches common folders or accepts `NANNERS_KHARVOX_DIR`.
- Added KHARVOX/umu-run preflight and diagnostics without making the Steam-only upstream compatibility assumption a hard failure.
- Normal **Launch DOOM** still goes through Heroic unchanged as the known-good fallback.

# NAnnersVRhub 0.4.0-dev10

- Added the first non-Steam storefront handler: **Heroic / GOG**.
- Added **DOOM (2016) — GOG / Heroic** using GOG app ID `1390579243`.
- Heroic discovery reads the existing `gog_store/installed.json` and per-game `GamesConfig/<appid>.json` metadata instead of hardcoding a Wine command.
- DOOM preflight validates `DOOMx64.exe`, the Heroic prefix, the configured Proton/Wine runner, and WiVRn.
- **Launch DOOM** hands the launch back to Heroic using Heroic's `heroic://launch?...&runner=gog` URI, preserving the user's configured `Proton-CachyOS-latest` runner and prefix.
- Store-aware core discovery now allows recipes that do not have a Steam AppID. Existing Steam behavior is unchanged.
- Added generic non-Steam live status text and store-aware diagnostics/UI launch messages.
- Added KHARVOX as an **experimental/unverified** guided VR step for this GOG copy; dev10 deliberately does not auto-install it yet because upstream currently documents Steam as the supported DOOM (2016) release.
- Added Heroic/GOG schema and handler regression coverage. **29 tests pass.**

# NAnnersVRhub 0.4.0-dev9

- Changed the generic **Launch game** path for Cyberpunk 2077, Fatekeeper, and Ready or Not from `steam://rungameid/<appid>` to `steam://launch/<appid>/dialog`.
- This lets Steam honor the game's configured launch-choice behavior: **Ask when starting game** can show the normal Steam chooser, while a saved/default choice is used when configured.
- NAnnersVRhub does not inject DirectX/Vulkan renderer flags for generic Steam launches, preventing duplicated options such as Ready or Not receiving DX11 from both Steam's launch choice and custom arguments.
- Skyrim VR keeps its proven MO2/SKSE bridge unchanged.
- Added regression coverage for the Steam launch-dialog URI.

# NAnnersVRhub 0.4.0-dev8

- Fixed the generic launch controls for Cyberpunk 2077, Fatekeeper, and Ready or Not.
- **Launch game** now opens the selected game's real Steam AppID through Steam, preserving that game's configured Steam/Proton launch options.
- The placeholder **Launch game tool** button is now hidden for games that do not define a dedicated tool. Skyrim still shows **Launch MO2**.
- Fatekeeper keeps its separate **Run UEVR injector** action alongside the now-functional **Launch game** button.
- Added regression coverage for generic Steam launching and kept Skyrim's dev6 bridge path unchanged.

# NAnnersVRhub 0.4.0-dev7

- Added a BananaNanners visual theme inspired by the channel artwork: banana-yellow accents, electric-blue secondary actions, dark Linux/VR panels, and a branded header.
- Bundled the supplied BananaNanners avatar as the application icon/header mark.
- Added live Skyrim workflow status for MO2 and Skyrim VR processes.
- Added an **Open bridge log** action for the Skyrim/MGO workflow.
- Preserved the proven dev6 Steam/MO2/SKSE launch bridge unchanged.
- Added package-data configuration so the branded image ships with installed builds.

# Changelog

## 0.4.0 development build 6

### Skyrim VR MO2 bridge launch
- Replaced dev5's non-working `steam -applaunch <shortcut-game-id> moshortcut://...` argument forwarding.
- **Launch Skyrim VR** now keeps Steam/Jackify responsible for starting the primary MO2 process, then forwards the selected SKSEVR entry through a short-lived second MO2 process in the Jackify shortcut's own Proton prefix.
- The handler derives the shortcut Steam root from `shortcuts.vdf`, locates `compatdata/<shortcut-appid>`, and reads that prefix's `config_info` to use the same Proton build.
- If MO2 is not already running, the bridge starts the proven `steam://rungameid/...` shortcut and waits for MO2 before forwarding `moshortcut://:<entry>`.
- Added `~/.local/share/vrhub/mo2-bridge.log` with timestamped bridge status instead of claiming success from a transient Steam PID.
- Diagnostics now report the detected non-Steam shortcut Proton prefix and Proton binary.
- No Steam shortcut or MO2 configuration is modified.

### Tests
- Added regression coverage for shortcut-prefix discovery and the dev6 bridge command.

## 0.4.0 development build 5

### Skyrim VR direct launch + MO2 state
- Added a dedicated **Launch Skyrim VR** action alongside **Launch MO2**.
- Dev5 reads MO2's portable `ModOrganizer.ini` without modifying it, reports the currently selected profile when present, and discovers configured executables.
- The Skyrim handler prefers an executable whose binary is `sksevr_loader.exe`, then an explicit SKSEVR/SKSE title; it never silently falls back to vanilla `SkyrimVR.exe`.
- Direct launch passes MO2's supported `moshortcut://:<executable>` argument through Steam's `-applaunch` path for the existing Jackify non-Steam shortcut. This is the real-system behavior to validate in dev5.
- Skyrim preflight now reports the detected MO2 active profile and SKSEVR/SKSE entry as informational readiness details.
- Diagnostics now include the MGO path, MO2 config path, active profile, Steam shortcut name/AppID/game ID, and selected Skyrim executable.
- Added CLI helpers: `nannersvrhub launch-tool skyrim-vr-mgo` and `nannersvrhub launch-game skyrim-vr-mgo`.

### Tests
- Added coverage for MO2 INI parsing, selected-profile decoding, SKSEVR preference, generated Steam/`moshortcut` launch command, and Skyrim diagnostics.
- 21 regression tests pass in this build.

## 0.4.0 development build 4

### Skyrim VR / MGO Steam-shortcut launch
- Renamed the Skyrim action from **Launch MGO** to **Launch MO2** so the UI names the exact program being opened.
- Replaced direct `proton run ModOrganizer.exe` launching with discovery of the Jackify-created non-Steam shortcut in Steam's `shortcuts.vdf`.
- The handler matches the shortcut by the detected MGO `ModOrganizer.exe` path, reads its binary 32-bit shortcut AppID, converts it to Steam's 64-bit shortcut game ID, and launches it with `steam://rungameid/...`.
- This preserves Jackify's own Proton prefix and Steam launch options (including WiVRn filesystem access, compat mounts, and any capture settings) instead of reimplementing them in NAnnersVRhub.
- Skyrim preflight now requires a matching **MO2 Steam shortcut** and shows the shortcut name/game ID when found.
- The GUI now reports that a launch request was sent to Steam rather than treating the short-lived Steam client process PID as proof that MO2 started.

### Tests
- Added binary `shortcuts.vdf` parsing coverage using the observed `SkyrimVRMGO3.8`/`ModOrganizer.exe` layout.
- Added regression coverage for shortcut AppID → 64-bit game ID conversion, preflight detection, and the generated Steam URI launch command.

## 0.4.0 development build 3

### Skyrim VR launch integration
- Added automatic MGO directory discovery for common Jackify/MGO layouts while keeping `NANNERS_MGO_DIR` as an explicit override.
- Added a handler-owned **Launch MGO** action in the GUI.
- Launch MGO uses Skyrim VR's Steam/Proton compatdata prefix instead of a separate Wine prefix.
- The launcher imports the recipe OpenXR environment and adds the MGO folder to `STEAM_COMPAT_MOUNTS` so Mod Organizer can see files outside the Steam library container.
- Proton discovery first consults the Skyrim VR compatdata `config_info`, then falls back to Proton Experimental / GE-Proton locations.
- Launch is blocked if required preflight checks fail.

### Tests
- Added regression coverage for MGO auto-detection and the generated Proton launch environment/command.

## 0.4.0 development build 2

### Modular game support
- Added `vrhub/handlers.py`, a small per-game hook registry so special behavior does not accumulate as one-off branches in the core installer or GUI.
- Added validated recipe `handler` metadata and a `guide` method for workflows that the hub should validate without directly owning the external modlist installer.
- Added optional recipe `[[links]]` metadata and game-specific notes in the GUI/details output.
- Preflight now supports optional/informational checks without incorrectly making the whole game NOT READY.

### Skyrim VR / MGO
- Added the first `skyrim-vr-mgo` recipe for Steam app 611670.
- Added WiVRn + Proton-prefix preflight for Skyrim VR.
- Added optional deep MGO checks through `NANNERS_MGO_DIR`.
- Deep checks verify the MGO folder, `ModOrganizer.exe`, and MGO's bundled `Open Composite XR - Incompatible with VR Performance Kit` mod directory.
- VR Performance Kit directory presence is reported as informational because actual enabled state belongs to the selected MO2 profile.
- The workflow deliberately leaves MGO installation/update ownership to Jackify/Wabbajack.

### Tests
- Added guide/handler schema tests.
- Added Skyrim handler preflight tests.
- Added a regression test that guided workflows refuse direct archive installation.
- 14 regression tests pass in this build.

## 0.4.0 development build 1
- Added recipe validation at startup.
- Added recipe-driven preflight checks for Steam discovery, Proton-prefix availability, OpenXR, WiVRn, and required component readiness.
- Added **Preflight** to the GUI and `nannersvrhub preflight <game>` to the CLI.
- Added non-destructive archive inspection for game-root mods.
- Added `[requirements]` metadata to Cyberpunk 2077, Fatekeeper, and Ready or Not.

## 0.3.0 foundation
- Transactional game-root installs with rollback.
- Windows-style ZIP path normalization.
- Component required-file sentinels.
- Diagnostics/logging and installed GUI/CLI launcher entry points.
