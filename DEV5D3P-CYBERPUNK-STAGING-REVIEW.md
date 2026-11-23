# Dev5D3-P — Cyberpunk Component Update Staging & Conflict Validation

## Goal
Prove safe multi-component Cyberpunk 2077 update staging, ownership checks, conflict prevention and interrupted batch rollback with synthetic ZIPs and disposable game fixtures only. Do not connect any live updater.

## Facts observed
- Approved parent Dev5D3-O commit b1966fd375719fb4f9ca6e8c1188d4692eea42ac, clean at fork.
- Cyberpunk's recipe defines 15 Nexus components. Cyber Engine Tweaks #107 and RED4ext #2380 are phase 1; CyberpunkVR Port #30093 is phase 2 and has a required stereo DLL.
- The existing live game-root installer identifies Nexus components by archive filename, maps ZIP wrappers to relative game-root destinations, rejects conflicting targets, and refuses to overwrite an already managed install.
- K/L's transaction engine is restricted to synthetic bytes in disposable /tmp fixture directories. Its rollback success does not prove real game or mod compatibility.
- No real future Nexus ZIP, version, SHA-256 pin, compatibility approval or live update authority was provided.

## Proposed defaults
- Accept only synthetic ZIP bytes, synthetic owned and untracked files, per-file component owners, recorded hashes, installed and future numeric versions and explicit hypothetical dependencies.
- Reuse existing ZIP preflight, component identity, game-root wrapper mapper and required-file validation on self-created private /tmp/nanners-dev5d3p-stage-* ZIP files. Reject unsafe, ambiguous or silently unmapped members.
- Preserve unrelated component files and all manual/untracked files. Reject cross-component ownership collisions, casefold and ancestor collisions, stale file hashes, missing previous owned files, invalid dependencies, no-op files and unsafe versions.
- Stage two fake updates (CET #107 and VR Port #30093), leave RED4ext #2380 unchanged, and simulate batch interruption/recovery through offline_transaction. All real compatibility and live execution flags stay false.
- Keep the production GUI unchanged. Add one preview-only Rehearse Cyberpunk component staging (TEST FIXTURE ONLY) action below the existing comparison disclosure, reset its result on game switch.

## Decision needed
The user explicitly started Dev5D3-P after approving O. This is an offline-fixture-only milestone. Real KDE desktop acceptance remains pending; no permission to update actual games was granted.

## Scope
- vrhub/cyberpunk_staging.py: non-executable component model, synthetic ZIP parsing and hashing, deterministic destination records, collision and ownership refusal, and interrupted batch recovery demo.
- tests/test_cyberpunk_staging_p.py: 32 synthetic Cyberpunk cases, including five crash points, cross-component and manual ownership, malformed or stale evidence, ZIP/path tricks, component ordering and non-live assertions.
- tests/manual_launcher_dev5d3p_preview.py: preserved prior O KDE checks with Cyberpunk-specific preview-only staging exercise and result, no production installer modifications.
- No changes to hub.py, downloads_gui.py, real recipes, state schemas, production installers, backups or approved worktrees.

## Safety / rollback
- Isolated branch dev/0.5.5-cyberpunk-component-staging, worktree ~/Projects/NAnnersVRhub-0.5.5-dev5d3p, forked from approved O commit b1966fd.
- Only synthetic bytes are staged/written in new private /tmp fixtures, never actual downloaded ZIPs, game directories, saves, Wine/Proton prefixes, saved scans or original backups.
- Existing Nexus key remains read-only in the development preview, never copied. Existing installer overwrite refusal remains intact.
- Source rollback: return to approved O without deleting persistent state or backups.
- Actual Nexus component compatibility, target mapping across real user mods, retired-file handling, VR functionality and production power-loss rollback are not verified.

## Tests
- Focused Cyberpunk + K/L offline recovery: 74/74 passed, including 32 new Cyberpunk tests.
- Full regression: 1,267 tests run; 1,266 passed, one skipped; no failures.
- Disposable nine-game KDE harness: 414/414 checks passed.
- Cyberpunk rehearsal and Fatekeeper synthetic safety screenshots visually inspected at 1630x1060. No overlapping controls; clearly labeled TEST FIXTURE ONLY.
- Shared preview state, scan history and archive folder preferences retained their original checksums during testing.

## Desktop acceptance
1. Dev5D3-P launches with archive-first scans, 15 Cyberpunk dependency rows, Compare versions and Nexus Updates unchanged.
2. Rehearse Cyberpunk component staging (TEST FIXTURE ONLY) is visible under Compare versions, initially Not run.
3. Clicking reports Cyberpunk staging PASSED; CET #107 and VR Port #30093; 2 synthetic ZIPs, 4 mapped destinations, 1 interrupted batch rollback.
4. RED4ext unchanged, manual scripts preserved, temporary fixture discarded, REAL COMPATIBILITY UNVERIFIED and LIVE UPDATE DISABLED appear.
5. Switching games clears the synthetic result and the expanded review scrolls without overlap.
6. Existing archive scans, Nexus key, integrity, KHARVOX, backup/recovery and installer safety gates remain intact; no actual games or mods are modified.

## Deferred
Actual live update execution, real compatible release validation, full game-root fresh backups and process locks, retired-file policy, manually customized mod merge decisions, physical power-loss testing, VR gameplay checks and release publication.
