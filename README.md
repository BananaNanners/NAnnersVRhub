# NAnnersVRhub 0.5.2

**NAnnersVRhub — Linux VR Compatibility & Mod Manager**

A Linux VR mod hub for Steam and Heroic/Epic games, developed on CachyOS + WiVRn + Quest 3.

Current recipes: Cyberpunk 2077, Fatekeeper, Hogwarts Legacy, Ready or Not, and Skyrim VR / Mad God's Overhaul.

## Hogwarts Legacy — Heroic/Epic + one-click injector

Launch Hogwarts through Heroic and wait for shader loading. Select it in the Hub
and click **Run UEVR injector**. Native Heroic installations reuse the game's saved
Wine/Proton runner and existing prefix; no file picker is needed. In UEVR, choose
**HogwartsLegacy**, select **OpenXR**, and click **Inject**. Close the in-game overlay
with **Insert** before checking immersion.

Flatpak Heroic and unsupported runner/prefix layouts retain the manual **Run EXE
on prefix** guide, with copyable injector path and an **Open Heroic** button. Failed
launches show their exit code and a bounded output tail. The Hub does not launch
a second copy of the game or change Heroic's saved settings.

The October 19 **user-reported** reference covers the one-click injector, rendering,
tracking, controller input and stereo depth. A short follow-up also confirmed spell
drawing and wrist-flick activation. Voice, body tracking, other gestures and longer
sessions remain untested. Local historical snapshots stay unchanged. See
[release notes](RELEASE-NOTES-0.5.2.md).

The matching **UEVR.zip** and **HogwartsLegacy.zip** from HL_UEVR v2.0.6 are still
installed separately through **Install mod file…** and **Install profile…**. The Hub
does not bundle the mods. Existing profiles are backed up separately from saves.

## In-app Hub updates

Choose **Hub updates…** above the tabs to check the official stable GitHub release,
download its source ZIP, and install a verified newer version without finding or
extracting an archive yourself. Startup checks are enabled by default and limited
to once per 24 hours; automatic downloads are optional and off by default.
Installation and restart always require your action. Game-mod updates remain
separate in Games.

For a first installation or an upgrade from 0.5.1, use the offline installer.
To test the in-app upgrade from dev4, keep dev4 installed and follow
[UPDATE-TESTING-0.5.2.md](UPDATE-TESTING-0.5.2.md) after the stable release is published:

```fish
unzip -n ~/Downloads/NAnnersVRhub-0.5.2-source.zip -d ~/Downloads
and cd ~/Downloads/NAnnersVRhub-0.5.2
and python install.py
and ~/.local/bin/nannersvrhub
```

Close the old Hub first. Downloads require HTTPS access to GitHub and its release
asset servers. PySide6/Python dependencies still use your existing installation.
The updater checks SHA256SUMS, GitHub asset digests when supplied, archive limits,
safe paths, complete resources and matching versions. Only an explicitly chosen
installation executes the downloaded application through the managed installer.
The previous installed version remains available for rollback.

The published stable release is currently **0.5.1**, older than this preview.
It can be downloaded for a real connection/checksum check; installation as an
update is disabled. A newer stable release will enable the install flow. Source
and wheel launches support checks/downloads; open the managed application-menu
entry for installation. See [UPDATE-TESTING-0.5.2-dev1.md](UPDATE-TESTING-0.5.2-dev1.md)
for acceptance checks, failure behavior and updater storage.

Dev2 keeps the newest independent recovery manager when rolling the application
back. It checks each release's own recipe inventory, so rollback from the new
five-game build to a four-game build and return both remain possible.

## Install 0.5.1

The final build promotes the accepted installer candidate. See
[RELEASE-NOTES-0.5.1.md](RELEASE-NOTES-0.5.1.md) and
[INSTALL-0.5.1.md](INSTALL-0.5.1.md) for setup, upgrades and rollback.

After downloading, run in fish:

```fish
unzip -n ~/Downloads/NAnnersVRhub-0.5.1-source.zip -d ~/Downloads
and cd ~/Downloads/NAnnersVRhub-0.5.1
and python install.py
```

Requires Linux, Python 3.11+ and working PySide6 in the selected Python
(`sudo pacman -S pyside6` on CachyOS/Arch if needed). The Hub installer itself
uses no sudo, pip or network access. Open **NAnnersVRhub** from the application
menu or run `~/.local/bin/nannersvrhub`.

App copies live in a permanent folder; saved tests, mod records and backups
stay in their existing location. Future extracted builds use `python install.py`
to upgrade. Close the Hub before switching versions. To select the previous
managed version, run `~/.local/bin/nannersvrhub-manage rollback`; repeating it
switches back. Automatic Hub downloads were outside the 0.5.1 release.

Recipes live in `vrhub/recipes/`. Regular wheel builds also include the recipes,
icon and app/CLI/guard/manager entry points. The source installer is the
recommended desktop workflow, with stable launchers and a menu entry.

The user confirmed dev1 independent startup, all four games listed and two games
running as expected, then reported **Pass** for the RC1 upgrade/rollback check.
See [candidate acceptance](RELEASE-CANDIDATE-0.5.1.md) for the historical procedure.

## Earlier 0.5.0 source release

The final source release promotes the accepted RC1 build, preserving its dev8
feature set and behavior. See [RELEASE-NOTES-0.5.0.md](RELEASE-NOTES-0.5.0.md),
[UPGRADE-0.5.0.md](UPGRADE-0.5.0.md) and the
[troubleshooting guide](TROUBLESHOOTING.md).

After downloading, run in fish:

```fish
unzip -n ~/Downloads/NAnnersVRhub-0.5.0-source.zip -d ~/Downloads
and cd ~/Downloads/NAnnersVRhub-0.5.0
and python -m vrhub.gui
```

The GUI needs the existing PySide6 installation (`sudo pacman -S pyside6` on
CachyOS/Arch). Python 3.11 or newer is required. Keep the extracted folder in a
stable location if Steam launch options refer to its `vrhub-check` script.
Saved installer state and local test history stay in their existing locations.

## Optional editable development installation

From this folder:

    python -m pip install -e .

Launch the GUI:

    nannersvrhub

Keep the source folder available for this editable install. The 0.5.0
distribution used extracted source/editable checkouts. Version 0.5.1-rc1 adds
complete wheel resources and the per-user desktop installer; see the new
installation guide above.

## 0.5.0 feature set

- VR System dashboard with read-only host inventory and WiVRn headset connection
  telemetry; controller input remains a live-test check.
- Compatibility profiles for the existing four game workflows, with current
  configuration checks kept separate from dated references and local tests.
- Explicit gameplay test recording/history with separate rendering, tracking,
  controller and stereo checks, plus historical setup snapshots.
- Bounded log diagnostics, including the observed OpenXR pose/validation failures
  and informational frame-discard status, with last matching-entry metadata.
- Combined text/JSON support reports, captured-snapshot time/age, explicit
  recollection, optional home-path replacement and excerpt omission.
- Readable 24-hour local times with zone labels, while JSON retains native
  timestamps. [Troubleshooting](TROUBLESHOOTING.md) explains evidence limits and
  the confirmed Fatekeeper/Cyberpunk menu workarounds.

The development entries below document how these features arrived. The final
release retains the accepted candidate's behavior. The documented menu/overlay
workarounds and experimental Cyberpunk limits remain part of the release.

## 0.5.0-dev8: report clarity and release-candidate preparation

Readable reports and the interface now use your computer's local timezone in **24-hour format**, such as `2026-10-18 16:43:28 PDT`. Stored/native JSON timestamps remain unchanged. Date-only bundled test references remain dates; timestamps embedded in log excerpts remain literal evidence. Log timestamps without a recorded timezone are clearly labelled rather than converted by assumption.

The support dialog keeps its captured time and age visible. **Collect new snapshot** reads sources again; **Copy report** and **Save report…** export the captured snapshot. Effective TEXT/JSON, excerpt and home-path options remain visible even after copying or saving. Excerpt-free filenames include `-no-excerpts` and use a local-time filename stamp.

Each recognized log finding also shows its **last matching entry in the inspected tail**, including when excerpts are omitted. Unknown timestamps stay unknown, and file modification time is kept separate. Historical counts do not automatically indicate an active error, a running game or a current gameplay failure.

See [DEV8-TESTING.md](DEV8-TESTING.md) for the final desktop checks and patches, and [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for report meanings and the four existing workflows. Dev8 prepares for 0.5.0-rc1; it remains a development build and does not certify new gameplay sessions.

## 0.5.0-dev7: combined support report

In Games -> Compatibility profile, choose **Create support report…** to preview a fresh VR system scan, the selected game's compatibility checks, bounded log findings and its latest local gameplay test with the historical setup snapshot. Each source keeps its own timestamps and evidence labels. **COMPLETE/PARTIAL** describes section collection, not gameplay readiness; no combined gameplay verdict is invented.

Copy or save the preview as text or JSON. Your Linux home path is replaced with `~` by default; you can restore full paths or omit log excerpts. These options change the preview/export without running another scan. Paths outside that home, headset names, test notes and relevant environment values may still contain personal information, so review before sharing. Collection does not upload, save gameplay tests or change game/runtime settings. Saved reports are private new files; existing destinations are preserved.

The dialog supports explicit log selection as well as the existing expected paths. Missing logs/history stay visibly missing, and a failed section leaves the rest usable. CLI: `python -m vrhub.cli support-report fatekeeper [--json] [--output NEW_FILE] [--no-excerpts] [--include-home-path]`. See [DEV7-TESTING.md](DEV7-TESTING.md) for desktop checks, export details and patches.

Fatekeeper's profile also records the October 18 confirmed sequence: **2D Screen Mode OFF, then close the in-game UEVR overlay with Insert**. The user's controller shortcut also opened WayVR's menu, so Insert is the documented test path. This guidance does not automatically set or verify those options, and the earlier October 17 bundled reference remains dated separately.

## Dev6 fix1: recognize Fatekeeper's rejected frame submissions

The submitted Fatekeeper log contained repeated `xrEndFrame failed: XR_ERROR_VALIDATION_FAILURE`, which dev6's initial signature set missed even in its inspected tail. Fix1 recognizes that validation error, including contextual numeric `res=-1` failures. It also identifies `xrBeginFrame ... XR_FRAME_DISCARDED` as informational: OpenXR defines it as a positive success status, even when UEVR logs it at error level. These findings do not identify the invalid parameter or automatically fix passthrough.

The supplied config also recorded `VR_2DScreenMode=true`. A one-setting test with UEVR's **2D Screen Mode** off is the next rendering investigation; fix1 does not edit that setting, synchronize frames differently, reinstall mods or change launch behavior. See [DEV6-FIX1-TESTING.md](DEV6-FIX1-TESTING.md).

## 0.5.0-dev6: read-only game-log diagnostics

In Games -> Compatibility profile, open **Log diagnostics…**. The Hub reads a bounded tail of CyberpunkVR Port's plugin log or Fatekeeper's expected UEVR profile log. **Choose log files…** supports explicit logs for any game, including Ready or Not and Skyrim; automatic paths for those two are not configured yet. Explicit selection replaces automatic discovery.

Findings show the file path, modification time, age, occurrence count, short excerpts, explanation and suggested next step. Cyberpunk's `xrEndFrame ... failed (res=-39)` finding includes the user-tested disabled-panel workaround and the reported game-menu passthrough limitation. The `Depth gate ... menu=1` message is informational. Generic OpenXR signatures also cover unavailable runtimes, missing extensions and missing graphics-requirements calls. This is a small signature set, not a general log parser.

Reads run in the background, never change files or settings, and do not update configuration status or saved gameplay tests. Logs older than 24 hours are marked stale; even recent logs may contain earlier sessions. No recognized error is not proof of successful VR. Reports are copied only when requested. CLI: `python -m vrhub.cli logs cyberpunk-2077 [--json]`, or `logs GAME --file /path/to/log.txt`. See [DEV6-TESTING.md](DEV6-TESTING.md) for testing, limits and patches. A combined support report remains the next milestone.

## 0.5.0-dev5: local gameplay test history

In Games -> Compatibility profile, use **Record live test…** to report success, partial success or failure, with separate results for VR rendering, head tracking, controller input and stereo depth. Notes are required for partial/failed tests. The latest local result appears above the bundled reference; **Test history…** shows and copies earlier entries and the local findings captured when they were recorded.

Entries persist across Hub restarts in a separate local history file beside the existing installer state. They do not overwrite bundled references, alter readiness checks, or automatically verify another session/configuration. Unchecked areas stay Not Tested. Cancel is read-only. Saves preserve concurrent writers and reject malformed existing history rather than replacing it with an empty file.

CLI commands are `record-test GAME --result success|partial|failure` (with explicit check/notes flags) and `test-history GAME [--json]`. See [DEV5-TESTING.md](DEV5-TESTING.md) for the complete workflow, persistence, limits and patches.

## Dev4 fix2: Ready or Not result and Cyberpunk panel workaround

Ready or Not now has its October 17 user-reported live-test reference. Cyberpunk's gameplay evidence reads **USER-REPORTED LIVE TEST — WORKAROUND REQUIRED (experimental)**. Its report prominently records the three panel settings that were disabled when the user first obtained an immersive view: General -> VR menu quad, HUD -> Enable HUD panel, and HUD -> World-space interactions / dialogs. The F10 overlay was also closed.

This records a successful immersive-rendering workaround, not a full stereo-depth or stability certification. The observed `xrEndFrame res=-39` and panel-dependent behavior suggest a mixed-layer submission issue; the exact fault in the installed build is not established. The Hub does not edit the mod's settings. See [DEV4-FIX2-TESTING.md](DEV4-FIX2-TESTING.md).

## Dev4 fix1: record the successful Fatekeeper live test

Fatekeeper now shows **USER-REPORTED LIVE TEST** with the October 17 result. The reference records the reported prefix runner (`proton-cachyos-slr`) without inventing an exact build version. This evidence label is stored profile data, not an automatic gameplay detector. Manual-review warnings and current local checks remain separate. See [DEV4-FIX1-TESTING.md](DEV4-FIX1-TESTING.md).

## 0.5.0-dev4: compatibility profiles for all four games

**Games -> Compatibility profile** now covers Cyberpunk 2077, Fatekeeper and Ready or Not alongside Skyrim VR/MGO. Reports distinguish gameplay evidence (**EXPERIMENTAL**, **UNVERIFIED**, or **USER-REPORTED LIVE TEST**) from current local checks. Skyrim's dated reference now includes the successful October 17 dev3-fix1 launch/controller test.

The added read-only checks inspect recorded Proton paths and the relevant mod files/install records: Cyberpunk's native plugin and all component phases; Fatekeeper's injector/backend plus recorded game-profile files; Ready or Not's recorded VRO PAKs. Missing Hub inventories remain incomplete. Manual-review items identify Steam/in-game/injector settings that are not inspected automatically; complete file fixtures normally report REVIEW REQUIRED for these new profiles.

No successful gameplay result is inferred for a new profile. The workflow guidance comes from the existing recipes, rather than a new upstream compatibility or version audit. See [DEV4-TESTING.md](DEV4-TESTING.md) for validation, status meanings, CLI commands and patches. Start live testing with the Fatekeeper compatibility report.

## Dev3 fix1: recognize the active MGO adapter variant

The active-profile scanner now accepts **Open Composite Unleashed for Skyrim VR** (including the reported numeric suffix `171182 5.0.4 2026`) alongside the older XR entry. It checks the enabled variant's own folder and flags multiple enabled recognized variants. VR Performance Kit's **FSR - Use with DLAA** and **CAS Sharpening - Default** names are now included in conflict checks. Disabled folders pass when their state is established from the active modlist. See [DEV3-FIX1-TESTING.md](DEV3-FIX1-TESTING.md) for the current package and patch instructions.

## 0.5.0-dev3: per-game compatibility profiles

In **Games**, select **Skyrim VR / MGO**, then **Compatibility profile** in the right pane. Refresh and copy the report to compare current local configuration with a dated, user-reported gameplay reference. The first profile documents runtime, Proton policy, adapter and launch route, plus requirements and validation notes. Dev3 initially documented Skyrim only; dev4 adds the remaining three profiles while retaining their existing workflows.

Skyrim checks the MO2 shortcut's own prefix and recorded Proton, the selected runtime/library file, simple leading runtime-import assignments in the shortcut's launch options, and enabled OpenComposite/VR Performance Kit state in the selected portable MO2 profile's modlist. Custom profile/base directories or ambiguous files remain unverified. The historical GE-Proton10-14 result does not force that version. The report does not execute launch options, change configuration, or certify a current gameplay session.

```sh
python -m vrhub.cli compatibility skyrim-vr-mgo
python -m vrhub.cli compatibility skyrim-vr-mgo --json
```

Compatibility metadata uses optional `[compatibility]` and `[compatibility.reference]` recipe tables. It is distinct from downloadable UEVR profiles. Reports use their own JSON schema version 1; VR System's scan schema stays at version 2. Exit 0 covers LOCAL CHECKS PASSED and REVIEW REQUIRED; other statuses exit 1. See [DEV3-TESTING.md](DEV3-TESTING.md) for status definitions, live testing and patch application.

## 0.5.0-dev2: live WiVRn connection status

The VR System dashboard now separates **Runtime selected**, **Server running**, **Headset connected/disconnected/unknown**, and **Controllers unverified**. While the VR System tab is open, live rows refresh every five seconds by default. Uncheck **Auto-refresh live status every 5 seconds** to pause polling; **SCAN MY VR SETUP** always performs a full host scan. Host and live timestamps are separate. Runtime selection changes trigger a fresh host scan. Copy/save exports the latest completed sample.

The live probe reads only WiVRn's read-only `HeadsetConnected` property and, when connected, `SystemName` through the user session bus. It uses the system `busctl` command, with automatic service startup and interactive authorization disabled and bounded request timeouts. It never starts WiVRn or an XR session, requests pairing, disconnects a headset, or reads PINs/paired keys/configuration. Missing `busctl`, inaccessible D-Bus, unsupported property versions, or malformed replies produce **UNKNOWN**, never a guessed disconnected state. Normal native CachyOS/Arch installations already include `busctl` with systemd. No new Python runtime dependency is added.

A typed WiVRn connection reply verifies connection status only. It does not prove controller tracking, graphics rendering, or game readiness. A WiVRn process/socket alone still cannot verify headset connection. Other runtimes retain conservative connection status until a supported telemetry probe is added.

Configured xrizer/OpenComposite custom paths are now included in host inventory, along with common `/opt` paths. Runtime library file paths are normalized for clearer reports.

JSON reports now use `schema_version = 2` with a `live` section: `runtime_selected`, `server_running`, `headset_connected` (true/false/null), `headset_name`, `headset_connection_verified`, `controllers_verified`, and `sampled_at`. `hardware_verified` remains false. CLI exit codes still refer to host prerequisite checks only.

Telemetry reference: [WiVRn D-Bus interface](https://github.com/WiVRn/WiVRn/blob/master/dbus/io.github.wivrn.Server.xml). The explicit Properties.Get call is used because `busctl get-property` has not consistently applied the automatic-start flag; see [systemd busctl source](https://github.com/systemd/systemd/blob/main/src/busctl/busctl.c).

## 0.5.0-dev1: VR System Dashboard

The GUI opens on **VR System**. **SCAN MY VR SETUP** runs a read-only background scan; **Games** contains the existing game/mod controls. Copy or save the report from the dashboard.

The first scan inventories the selected OpenXR manifest and library, host OpenXR/Vulkan loaders, WiVRn/Monado/SteamVR server processes, WiVRn/Monado IPC sockets, configured host OpenVR adapter paths, xrizer/OpenComposite common locations, Steam, and integration commands on PATH. Runtime discovery checks architecture-specific manifests, XDG directory precedence, and explicit overrides.

From the source folder (no pip install required):

    python -m vrhub.gui
    python -m vrhub.cli scan
    python -m vrhub.cli scan --json

Scan statuses are **NOT READY** for failed host prerequisites, **NEEDS CHECKS** for unresolved host prerequisites, and **HOST CHECKS PASSED** when those file/library checks pass. The CLI exits 0 only for HOST CHECKS PASSED; otherwise it exits 1. This does not certify game readiness, graphics rendering, Proton access, headset connection, or controller tracking. Hardware is explicitly **UNVERIFIED** in dev1; use your runtime manager and a live VR app to verify it. Use the existing game **Preflight** separately.

The scan never starts a runtime, changes launch options, connects to the compositor, loads the runtime library, or installs anything. PATH and common-directory inventories may miss custom/Flatpak tools and game-local Windows adapters. Relevant environment settings reflect the Hub process, not individual Steam game launch options. Reports include local paths; review them before sharing.

Dev2 adds WiVRn connection telemetry; dev3 starts per-game compatibility profiles. Live controller input verification remains a later milestone.

Detection references: [Khronos OpenXR loader runtime discovery](https://github.com/KhronosGroup/OpenXR-SDK-Source/blob/main/specification/loader/runtime.adoc), [WiVRn Steam integration](https://github.com/WiVRn/WiVRn/blob/master/docs/steamvr.md).

## 0.4.0 additions

### Game-handler architecture

Most games remain completely recipe-driven. Games that need special Linux/VR checks can now opt into a small handler with:

    handler = "skyrim-vr"

Game-specific behavior lives in `vrhub/handlers.py`, rather than adding Skyrim/Cyberpunk/etc. branches throughout `hub.py` and `gui.py`. The first handler hooks are:

- extra preflight checks;
- game-specific notes;
- whether a recipe supports direct archive installation.

A new `method = "guide"` workflow is available for setups that should be validated by the hub but remain owned by another installer.

### Skyrim VR + Mad God's Overhaul

The `skyrim-vr-mgo` recipe is a guided integration. Jackify/Wabbajack remains responsible for installing/updating MGO; NAnnersVRhub checks and launches the surrounding Linux VR stack.

Run:

    nannersvrhub preflight skyrim-vr-mgo

By default it checks Skyrim VR discovery, the Proton prefix and WiVRn. It also auto-detects common MGO directories by looking for `ModOrganizer.exe`. If auto-detection does not find yours, override it before launching the hub:

    set -x NANNERS_MGO_DIR "/path/to/your/MGO"
    nannersvrhub

The Skyrim handler checks for `ModOrganizer.exe` and MGO's bundled `Open Composite XR - Incompatible with VR Performance Kit` directory. The GUI exposes **Launch MO2**, which starts the Jackify-created non-Steam shortcut through Steam, plus **Launch Skyrim VR**. In dev6 the game action first ensures the real Jackify MO2 shortcut is running, then forwards MO2's configured SKSEVR/SKSE entry through a short-lived MO2 process in that shortcut's own Proton prefix. The Hub reads the active MO2 profile and executable list from `ModOrganizer.ini` without editing it. Bridge status is written to `~/.local/share/vrhub/mo2-bridge.log`. Configured VR Performance Kit directories are reported as an informational warning because enabled/disabled state is MO2-profile-specific.

This workflow is built around WiVRn + xrizer + MGO's bundled OpenComposite. It does not replace Jackify and does not copy or redistribute the MGO modlist.

### Preflight

Recipes can declare runtime requirements. Check a game without changing anything:

    nannersvrhub preflight cyberpunk-2077

The GUI has the same **Preflight** action. It checks the Steam install, Proton prefix, OpenXR/WiVRn state, required component readiness, plus any game-handler checks.

### Inspect an archive before installing it

For game-root recipes such as Cyberpunk, inspect an archive without touching the game:

    nannersvrhub inspect cyberpunk-2077 --file ~/Downloads/<archive>.zip

The report shows which component was detected, how many files are in the archive, how many would actually be installed, which game-root trees are targeted, required sentinels, and sample destinations.

### Validated recipes

Recipe TOML is validated at startup. Bad app IDs, duplicate components, unsafe sentinel paths, unknown handlers, unsupported methods, malformed links and malformed requirements are rejected before install work begins.

## Existing useful commands

    nannersvrhub status
    nannersvrhub verify cyberpunk-2077
    nannersvrhub diagnose cyberpunk-2077
    nannersvrhub preflight skyrim-vr-mgo
    nannersvrhub updates
    nannersvrhub nexus-key
    nannersvrhub install ready-or-not --file ~/Downloads/<mod>.zip
    nannersvrhub install fatekeeper --file ~/Downloads/UEVR_FK.zip
    nannersvrhub install-profile fatekeeper --file ~/Downloads/SLASHER-Win64-Shipping.zip
    nannersvrhub launch-injector fatekeeper
    nannersvrhub launch-tool skyrim-vr-mgo
    nannersvrhub launch-game skyrim-vr-mgo

## 0.4.0 release-candidate scope

The public game list is intentionally limited to VR workflows that have been verified end-to-end on the test system:

- Cyberpunk 2077
- Fatekeeper
- Ready or Not
- Skyrim VR / Mad God's Overhaul

The experimental DOOM (2016) GOG/Heroic + KHARVOX recipe is not shipped in the public recipe list because the KHARVOX intro and game launch worked but actual DOOM gameplay did not enter native stereo VR on the tested Proton/WiVRn path. The Heroic/GOG support code remains in the source tree as development groundwork for a future verified integration.

## Tests

    python -m unittest discover -s tests -v

See `CHANGELOG.md` for development notes.


## Generic Steam launching (dev9)

For Cyberpunk 2077, Fatekeeper, and Ready or Not, **Launch game** asks Steam to launch the app through `steam://launch/<appid>/dialog`. This intentionally leaves renderer selection and other launch choices to Steam. If a game is set to **Ask when starting game**, Steam can show its normal chooser; if a default choice is saved, Steam uses it. NAnnersVRhub does not add DX11/DX12/Vulkan flags on this path.

## 0.4.0-dev8 UI

The Qt GUI now uses the BananaNanners visual theme derived from the project/channel artwork, with a branded header, dark panels, yellow/blue accents, and live Skyrim/MO2 launch status.
