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
