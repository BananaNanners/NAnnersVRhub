# NAnnersVRhub 0.5.0-dev6 testing

Dev6 adds read-only, per-game log evidence. It does not repair the Cyberpunk
menu behavior, change Proton/runtime settings, or rewrite your dev5 test history.

## Run

Extract the source ZIP in Downloads, then run in fish:

```fish
cd ~/Downloads/NAnnersVRhub-0.5.0-dev6
python -m unittest discover -s tests -v
python -m vrhub.gui
```

Use your existing PySide6 installation. No new runtime dependency is needed.
Your existing live-tests.json is read from the same location as dev5.

## First desktop check: Cyberpunk

1. Open Games -> Cyberpunk 2077 -> Compatibility profile. Confirm your saved
   Partial Success record is still visible, including all four passed checks.
2. Click **Log diagnostics…**. It automatically reads the tail of
   `bin/x64/cyberpunkvrport.log` in this game's Steam directory.
3. If the inspected tail contains `xrEndFrame mono submit failed (res=-39)` or
   `XR_ERROR_POSE_INVALID`, expect a recognized invalid-pose finding with a count,
   up to three excerpts, and the disabled-panel workaround. An old error may
   remain after a successful run; the report does not call it a current failure.
4. Confirm the report describes the menu limitation: opening the game menu caused
   passthrough in the October 18 user test; exiting it restored full VR. Dev6
   records that limitation, and does not claim to fix it.
5. Click **Copy log report** and review the text before sharing. Paths and short
   matching excerpts are included; the whole log is not copied.
6. Use **Refresh** after a new test, or **Choose log files…** to inspect another
   known text log. Canceling the picker preserves the displayed report.
7. Close diagnostics. Your compatibility status and gameplay history should be
   unchanged. A diagnostic scan never saves a test result.

The word "mono" in the plugin's error message is preserved as evidence. The Hub
does not use it to infer your selected stereo mode.

## Expected automatic paths and coverage

| Game | Automatic source | Other files |
| --- | --- | --- |
| Cyberpunk 2077 | `<Steam game>/bin/x64/cyberpunkvrport.log` | Choose RED4ext/CET or another text log explicitly |
| Fatekeeper | `<game prefix>/drive_c/users/steamuser/AppData/Roaming/UnrealVRMod/SLASHER-Win64-Shipping/log.txt` | Choose a community build's alternate path explicitly |
| Ready or Not | Not configured in dev6 | Choose a log explicitly |
| Skyrim VR / MGO | Not configured in dev6 | Choose a log explicitly; dev6 does not guess between base-game and MO2 prefixes |

Explicit selection replaces automatic discovery and accepts one to four files.
The selected game determines the advice; the user supplies the association of a
manual file with that game. Nothing recursively scans your game/prefix/home.

The initial signatures are the exact OpenXR symbols below, or a failed OpenXR
call with `res=` / `result=` and the corresponding numeric code:

- `XR_ERROR_POSE_INVALID` (-39)
- `XR_ERROR_RUNTIME_UNAVAILABLE` (-51)
- `XR_ERROR_EXTENSION_NOT_PRESENT` (-9)
- `XR_ERROR_GRAPHICS_REQUIREMENTS_CALL_MISSING` (-50)

Numeric codes without an OpenXR call/failure context are ignored. Cyberpunk's
`Depth gate ... menu=1` is an informational finding, not a failure or proof of the
actual menu-quad setting. Generic signatures on another game never receive the
Cyberpunk-specific F10 workaround. Unrecognized loader, script, crash, controller
and GPU errors are outside this initial signature set and need manual review.

## Evidence and read limits

- Each file reads at most the last 512 KiB plus a two-byte encoding probe. Up to
  10,000 retained lines are analyzed, limited to their first 4,096 characters.
  Partial leading lines are discarded. Counts apply only to the inspected tail;
  excerpt line numbers are relative to the retained tail, not the whole file.
- Each finding retains the last three matching excerpts, at most 300 characters
  each. ANSI/control sequences are removed; excerpts are shown as literal text.
- UTF-8 (with replacement for invalid bytes) and BOM-marked UTF-16 are accepted.
  Binary files, non-regular files and direct file symlinks are rejected. Automatic
  candidates that resolve outside the game's directory/prefix are rejected.
  Choose a symlink's real target explicitly if you need it inspected.
- File modification time is shown in UTC, with age in seconds. More than 24 hours
  old is STALE; over five minutes in the future is flagged as uncertain. Neither
  a recent modification time nor an error excerpt identifies a gameplay session.
- Refresh reads again. There is no automatic poll, upload, log deletion, game
  launch, settings edit or persisted diagnostics cache. Closing while a scan is
  running waits for that worker to finish safely.
- Configuration reports and test snapshots keep their existing schemas. Log
  diagnostics has a separate JSON schema version 1, with source metadata,
  findings, excerpts and explicit read limits.

No readable log -> NO READABLE LOG EVIDENCE. A readable log with no recognized
signature -> NO KNOWN SIGNATURES FOUND. Any recognized signature, including an
informational menu message -> RECOGNIZED LOG EVIDENCE. None is a gameplay verdict.

## CLI

```fish
python -m vrhub.cli logs cyberpunk-2077
python -m vrhub.cli logs fatekeeper --json
python -m vrhub.cli logs ready-or-not --file /path/to/game.log
python -m vrhub.cli logs cyberpunk-2077 --file /path/to/plugin.log /path/to/loader.log --json
```

Exit 0 means at least one selected log was readable (including empty); exit 1
means no readable log or an invalid request. Error findings do not change this
exit code into a gameplay pass/fail result. In a multi-file scan, review each
file's status even when the command exits 0.

## Existing checkout

Choose one patch:

- `dev6-from-dev5.patch`: incremental from delivered dev5 (1bf57af).
- `dev6.patch`: cumulative from clean v0.4.0 (2e320ac).

From an existing dev5 checkout:

```fish
git status --short
git apply --check ~/Downloads/NAnnersVRhub-0.5.0-dev6/dev6-from-dev5.patch
git apply ~/Downloads/NAnnersVRhub-0.5.0-dev6/dev6-from-dev5.patch
python -m unittest discover -s tests -v
python -m vrhub.gui
```

Preserve unrelated local edits. If the patch check fails, stop and share the
error. Do not apply both patches. The extracted source can be tested directly.

## Technical references and limits of the workaround

The OpenXR result mappings come from the
[Khronos XrResult reference](https://registry.khronos.org/OpenXR/specs/1.1/man/html/XrResult.html).
The Cyberpunk log path is documented by the
[port's README](https://github.com/dariulone/cyberpunk-vr-port#logs).
The UEVR profile/log convention comes from
[Framework.cpp](https://github.com/praydog/UEVR/blob/master/src/Framework.cpp)
(`get_persistent_dir` and the logger constructor); a modified community build can
use a different path.

The panel workaround and game-menu passthrough limitation come from this
project's user-reported October 17–18 WiVRn tests. An invalid pose does not by
itself prove the suspected mixed-layer conversion bug or identify the installed
runner's exact fault. The diagnostic advice does not recommend replacing the
working Proton build or claim a permanent upstream fix.

## Validation

166 unit tests pass, including 20 new diagnostics tests covering signature
context/false positives, game-specific advice, missing/empty/unreadable/stale and
future logs, byte/line/excerpt limits, text encodings, binary/special-file/symlink
handling, CLI JSON and unchanged settings/history. Qt offscreen smoke checks cover
the actual modal button route, automatic/manual reads, picker cancel, refresh,
copy, missing logs, and safe close during a running scan. The dialog was visually
checked. Desktop testing against the actual installed games remains the next step.
