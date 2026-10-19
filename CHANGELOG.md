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
