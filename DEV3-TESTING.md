# NAnnersVRhub 0.5.0-dev3 testing

For the corrected package, see [DEV3-FIX1-TESTING.md](DEV3-FIX1-TESTING.md).

Dev2 passed the user's CachyOS/WiVRn/Quest 3 connection transition test:
CONNECTED -> UNKNOWN -> CONNECTED. Dev1's Skyrim VR/MGO launch also passed
with both controllers working. Dev3 adds the first documented compatibility
profile, starting with that Skyrim VR/MGO reference.

## Run

Extract the source ZIP in Downloads, then run in fish:

```fish
cd ~/Downloads/NAnnersVRhub-0.5.0-dev3
python -m unittest discover -s tests -v
python -m vrhub.gui
```

Use your existing PySide6 installation. No new runtime dependency is required.
The package does not require changing Proton, WiVRn, the modlist, or Steam settings.

## First live check

1. Connect your Quest through WiVRn normally.
2. Open Games, select Skyrim VR / Mad God's Overhaul, then select
   **Compatibility profile** in the right pane.
3. Click **Refresh compatibility**, then **Copy compatibility report** and paste
   the report for review.
4. Check that the MO2 prefix belongs to its Steam shortcut, rather than base
   Skyrim app 611670. The tested shortcut had AppID 4052365288, but the code
   discovers it from the matching ModOrganizer.exe shortcut; it is not hardcoded.
5. Check the currently recorded Proton. GE-Proton10-14 is the historical reference;
   a different build calls for review and is not automatically changed or blocked.
6. Review the active MO2 profile's OpenComposite and VR Performance Kit findings.
   A mod folder alone does not prove the mod is enabled. Default portable MO2
   profile layouts are inspected via modlist.txt. Custom base/profile roots,
   unreadable or ambiguous files stay unverified and should be reviewed in MO2.
7. The shortcut runtime-import check recognizes a simple leading assignment such
   as `PRESSURE_VESSEL_IMPORT_OPENXR_1_RUNTIMES=1 %command%`, optionally using
   `env` and a launcher such as gamemoderun. Complex shell wrappers or a missing
   declaration require manual review; the Hub process's environment is not proof
   of the shortcut's configuration. It never executes the options or changes them.
8. Use Preflight, then launch Skyrim VR normally and confirm VR rendering and
   both controllers still work. This final step needs your machine/headset.

Do not disable a working mod or change Proton merely to manufacture a test failure.

The reference section describes the user's October 6 test; it is not a new live
gameplay claim. The report's sampled timestamp applies to local file/config checks.
VR System retains the separate live headset connection check.

## Status meanings

| Status | Meaning |
| --- | --- |
| LOCAL CHECKS PASSED | Current profile configuration checks passed; gameplay remains unverified. |
| REVIEW REQUIRED | A notice needs review, such as a different Proton build or a complex launch wrapper. |
| INCOMPLETE | Required evidence is unavailable, such as the active profile's modlist. |
| NOT READY | A checked requirement failed, such as missing shortcut prefix, wrong runtime, disabled OpenComposite, or enabled VR Performance Kit conflict. |
| NOT DOCUMENTED | This game has no documented compatibility profile yet; its guide, Preflight, and install/launch workflows remain available. |

Priority is NOT READY, then INCOMPLETE, then REVIEW REQUIRED. In fix1, disabled
VR Performance Kit folders pass when the active modlist establishes their disabled
state; unresolved profile evidence remains unverified.

CLI equivalents:

```fish
python -m vrhub.cli compatibility skyrim-vr-mgo
python -m vrhub.cli compatibility skyrim-vr-mgo --json
```

Exit 0 means LOCAL CHECKS PASSED or REVIEW REQUIRED; exit 1 means NOT READY,
INCOMPLETE, or NOT DOCUMENTED. Neither exit status certifies live gameplay.
Copy diagnostics includes the compatibility report for a documented profile.
Compatibility metadata is separate from the installable UEVR game-profile ZIPs.

## Apply to your existing checkout

The archive contains two patches. Choose one, based on your current source:

- `dev3-from-dev2.patch`: incremental update from the delivered 0.5.0-dev2 source.
- `dev3.patch`: cumulative update from clean v0.4.0 (`2e320ac`).

For a dev2 checkout, in your repository:

```fish
git branch --show-current
git status --short
git apply --check ~/Downloads/NAnnersVRhub-0.5.0-dev3/dev3-from-dev2.patch
git apply ~/Downloads/NAnnersVRhub-0.5.0-dev3/dev3-from-dev2.patch
python -m unittest discover -s tests -v
python -m vrhub.gui
```

Use the existing dev/0.5.0 branch. Preserve unrelated local work. If the patch
check fails, stop and share the error; do not force it. For clean v0.4.0,
substitute `dev3.patch`. Do not apply both patches. The complete source can also
be tested independently without modifying your repository.

## Validation before delivery

- 89 unit tests pass, including a complete filesystem fixture with binary Steam
  shortcut, MO2 profile, enabled/disabled mods, and recorded Proton prefix.
- Covered enabled conflicts, missing/duplicate modlists, custom profile roots,
  base-game versus shortcut prefix, runtime mismatch/missing library, stale
  runtime changes, launch-option ambiguity, read-only behavior, schema validation,
  JSON exit semantics, and escaped report content.
- Qt offscreen smoke checks passed for selection, refresh, clipboard copying,
  clearing a prior pass after losing evidence, undocumented games, tab switching,
  and close. The rendered Compatibility profile view was inspected.
- Incremental and cumulative patches were checked against their baselines, and
  the extracted deliverable was tested before saving.
- Live dev3 validation on CachyOS/WiVRn/Quest remains the next user check.
