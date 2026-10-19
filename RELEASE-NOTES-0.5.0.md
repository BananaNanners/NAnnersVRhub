# NAnnersVRhub 0.5.0

Released as a final source archive on October 18, 2026 (America/Los_Angeles).
The accepted RC1 build freezes the dev8 feature set. Final promotion changes
the version and release documentation while preserving that runtime behavior.

NAnnersVRhub helps make Windows VR games and VR mods understandable, testable and
launchable on Linux. The project's test setup is CachyOS, WiVRn and Meta Quest 3.
Jackify/Wabbajack remains responsible for MGO installation/updates, and WiVRn
remains responsible for headset streaming/runtime services.

## Included in 0.5.0

- **VR System dashboard:** read-only runtime/library, tool and adapter inventory,
  host prerequisite checks and WiVRn D-Bus headset connection status. Connection
  telemetry does not automatically verify controller poses/input or rendering.
- **Per-game compatibility:** current configuration findings alongside separately
  dated references for Skyrim VR/MGO, Fatekeeper, Ready or Not and experimental
  CyberpunkVR Port. The existing Proton selections/prefixes remain in use.
- **Local gameplay history:** explicit Success/Partial Success/Failure records,
  four independent gameplay checks, notes and historical setup findings. Saving
  a result never silently changes configuration readiness or an older reference.
- **Log diagnostics:** bounded read-only tails, named error/status explanations,
  counts, source metadata and last matching-entry timestamps. Unknown timezones
  stay unknown; historical counts do not imply an active failure or running game.
- **Combined support reports:** fresh independent source sections, text/JSON
  preview/copy/save, home-prefix replacement, optional excerpt omission and
  visible snapshot time/age. Collect new snapshot recollects; Copy/Save export
  the captured evidence. New report files preserve existing destinations.
- **Time clarity:** readable/interface timestamps use the system's local zone in
  24-hour format; JSON retains native source timestamps and offsets.

## Compatibility evidence carried forward

These are dated user-reported tests on one setup. The aggregate RC1 acceptance
is recorded separately below; it does not replace the detailed per-game records.

| Workflow | Dated project evidence | Conditions/remaining limits |
| --- | --- | --- |
| Skyrim VR / MGO | October 17 launch/controller success with the recognized Unleashed adapter | Use the MO2 shortcut's own prefix/Proton and active profile; one bundled adapter enabled, recognized VR Performance Kit variants disabled |
| Fatekeeper | October 17 success; October 18 full-VR recovery and saved SUCCESS report | 2D Screen Mode OFF, close the in-game UEVR overlay using Insert; the reported controller shortcut also opens WayVR |
| Ready or Not VRO | October 17 reported mission VR/controller success | DirectX 11 workflow; load a mission before U entry, Home exit; actual Steam/in-game settings require review |
| CyberpunkVR Port | October 17 immersive recovery; October 18 all four local gameplay checks passed in a PARTIAL SUCCESS record | Experimental; tested HUD/menu panels disabled and F10 closed; opening the game menu caused passthrough and exiting restored full VR |

The October 18 dev8 desktop support JSON validated excerpt omission, retained
last-occurrence metadata, home-path replacement, native UTC timestamps and the
saved Fatekeeper SUCCESS record. Old log findings remained historical; exact
overlay/frame-validation fault attribution is still unconfirmed.

## Known limits

- Required file presence/inventory checks do not prove DLL/plugin loading or
  installed release versions. Manually configured Steam and in-game settings
  may remain REVIEW REQUIRED after a successful user test.
- Automatic log paths cover CyberpunkVR Port and the expected Fatekeeper UEVR
  profile log. Skyrim and Ready or Not use explicit file selection. Community
  builds/custom paths can require manual selection for any game.
- Signature recognition is intentionally limited. No known signature found
  does not prove error-free rendering. Tail truncation, line limits, timezone
  ambiguity and old/multi-session logs limit comparisons.
- The confirmed Fatekeeper/Cyberpunk overlay workarounds remain documented
  test conditions. This release does not repair upstream frame submission or a WayVR
  shortcut collision, and does not claim those errors permanently resolved.
- Home-prefix replacement is not complete anonymization. Review names, notes,
  paths outside the Linux home and any retained excerpts before sharing.
- This release is delivered and validated as a source archive/editable
  checkout. Keep that folder available for its resources and any existing
  Steam guard path. A self-contained non-editable wheel/system package is not
  part of the 0.5.0 distribution.

## State and report compatibility

Existing `~/.local/share/vrhub/state.json` and `live-tests.json` remain in place.
If VRHUB_STATE points elsewhere, gameplay history follows that file's parent.
No automatic migration or game/settings rewrite is part of this release.

Host scan JSON schema remains 2. Compatibility, log and combined support schemas
remain 1, with additive last-occurrence metadata from dev8. Local history schema
remains 1. Stored results/timestamps are not rewritten for local-time display.

## Build validation and desktop acceptance

The release's unit suite has 209 tests, covering the four recipe workflows,
read-only telemetry, archive checks, history persistence, bounded log evidence,
support exports and local-time/DST presentation. Extracted-source and editable
startup, resources and GUI report exports were checked during candidate
preparation. These automated checks remain distinct from live desktop evidence.

On October 18 the user confirmed that RC1 listed all games and preserved saved
history. At 18:36 PDT, the user replied **Pass** to the requested gameplay smoke
test covering the four existing workflows. This is recorded as aggregate
user-reported acceptance; no new per-game breakdown or automatic measurements
are invented. Known Cyberpunk menu behavior remains in the conditions above.

The [RC1 checklist](RC1-CHECKLIST.md) remains as the historical acceptance
procedure. For a later issue, report the exact trigger, actual versus expected
behavior, version and a reviewed fresh support export. See
[UPGRADE-0.5.0.md](UPGRADE-0.5.0.md) for final source/patch instructions.
