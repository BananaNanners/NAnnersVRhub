# Dev5D3-O — UEVR Profile Update Staging & Recovery Validation

## Goal
Add an **offline-only, disposable whole-directory UEVR profile staging and recovery rehearsal** for Fatekeeper and Hogwarts Legacy. Distinguish UEVR profile ZIP updates from UEVR injector packages, and preserve original configuration files, directory topology, empty folders and permissions during interrupted recovery tests. Do NOT enable any live game-profile update.

## Facts observed
- Parent: desktop-approved Dev5D3-N, Git commit \`b5b20a08195cec1c145ba4d0f0fc90b9be6daa8a\` on a clean \`dev/0.5.5-pinned-staging-compat\` worktree.
- Fatekeeper profile recipe points to \`Roaming/UnrealVRMod/SLASHER-Win64-Shipping\`. Hogwarts Legacy profile recipe points to \`Roaming/UnrealVRMod/HogwartsLegacy\`. Both have separate UEVR injector and profile dependency components. Both already have read-only archive/version review.
- Existing \`profile_safety._archive_entries()\` detects the ZIP's selected \`config.txt\` anchor, unwraps the profile directory, rejects ambiguous/colliding paths and uses \`install_review._zip_preflight()\` for unsafe ZIP metadata. Existing \`profile_safety._snapshot()\` and \`_verified_copy()\` inventory complete directories and content SHA-256, including empty folders.
- Existing live \`profile_safety.install()\` deliberately blocks already-managed profile replacement and has a hard execution gate. Neither it nor the backup/restore backend may be changed or invoked by this milestone.
- The Dev5D3-K/L \`offline_transaction.fixture_sandbox()\` restricts synthetic mutations to marked private \`/tmp/nanners-dev5d3k-fixture-*\` sandboxes. Per-file replacement alone cannot prove the whole-profile directory-swap case.
- Real candidate ZIP release identity, real game-build compatibility, Proton/Wine prefix identity and working injector compatibility remain unverified; synthetic declarations are not evidence of those facts.

## Proposed defaults
- Support only synthetic profile ZIP **bytes** supplied directly to the staging model, not arbitrary disk paths or user Downloads. Require an exact fixture SHA-256, unique profile \`config.txt\` wrapper, bounded regular ZIP members, and zero discarded outside-wrapper files. Reuse the existing profile archive parser in a private temporary directory.
- Require exact Hub-like ownership evidence: SHA-256 for each current synthetic profile file **and** a complete declared original directory inventory. Any untracked or manually changed file or unexpected empty folder blocks staging.
- Compare strictly numeric synthetic versions, declared synthetic game builds and separately declared injector compatibility. Unknown, older, unapproved or incompatible values block staging; even matching declarations leave \`real_game_compatibility_verified=False\`.
- Never silently merge configuration files or prune obsolete files. A new \`config.txt\` replaces the test copy only within a fixture, while the **complete old configuration remains recoverable**. Removal of any old file absent from the new profile requires an exact explicit \`explicit_removals\` list.
- Stage an entire synthetic profile tree, SHA-256 validate it and a verified whole-directory original backup, and record a sealed on-disk intent journal before any two-step directory swap. Preserve all original file/directory permission modes. The two renames are **not** all-at-once atomic.
- Recheck the source review fingerprint, complete original snapshot, backup snapshot and staged snapshot before swap. Serialize fixture execution and recovery under the existing fixture lock. Check private fixture free space before any backup or staging write.
- Recovery inspects *actual* fixture filesystem state, not just journal progress, to handle interruptions after either rename. Verify backup, displaced tree, activated tree, and permissions before altering anything. Refuse unexpected edits, unsafe symlinks, missing originals or damaged backups. Interruptions during rollback itself can be resumed. Incomplete preparation is aborted with partial backups explicitly untrusted.
- Keep UEVR injector files entirely out of profile mutation/staging. No live installer, download, update, new real backup, Proton prefix write or state mutation is enabled.
- Retain the existing production UI. Add only a **preview-only** \`Rehearse UEVR profile staging (TEST FIXTURE ONLY)\` control below Compare versions, with clear live-update-disabled language and result reset on switching games.

## Decision needed
The user explicitly requested implementation of Dev5D3-O after desktop approval of N. No consequential blocker to the conservative synthetic-only implementation. **Manual KDE desktop acceptance is still required**; this checkpoint has not been publicly released or granted live execution authority.

## Scope
- New \`vrhub/uevr_profile_staging.py\`: synthetic ZIP SHA validation and profile wrapper mapping, strict current installed file/directory ownership check, explicit version/build/injector compatibility declarations, explicit file-removal policy, a complete staged tree with verified whole-directory backup, serialized fixture-only directory swap, sealed transaction journal, fail-closed recovery, simulated process interruptions and a two-game fixture demonstration.
- New \`tests/test_uevr_profile_staging_o.py\`: model refusal cases (bad ZIPs, paths, wrong version/build/injector declarations, modified/manual files, untracked directories, unapproved deletions) and actual whole-directory recovery cases (after journal, backup, prepared, displaced, activated, committed, mid-rollback, and a genuine child-process exit between renames). Includes backup/journal tampering, symlinks, altered modes, free-space preflight and stale source evidence.
- New \`tests/manual_launcher_dev5d3o_preview.py\`: extends prior N's nine-game isolated KDE harness and adds a **preview-only**, manual-click Fatekeeper/Hogwarts profile rehearsal. Real selected game paths and saved profile directories are never passed into the synthetic staging engine.
- No edits to approved live \`profile_safety.py\`, \`hub.py\`, \`downloads_gui.py\`, source recipes, installer backends, existing tests, old checkpoints, or recovery logic.

## Safety / rollback
- New worktree \`~/Projects/NAnnersVRhub-0.5.5-dev5d3o\` on \`dev/0.5.5-uevr-profile-staging\`, forked from approved N commit \`b5b20a0\`. Source rollback is simply to N, without resetting any saved Hub state, scans, preferences or backups.
- The new engine writes **only** synthetic bytes to its own disposable \`/tmp\` fixture directories. It does not consume real Downloads ZIPs, operate on the user's game prefix, use real Nexus credentials, or call live UEVR installation/restore functions.
- Original synthetic configuration files and extra managed files are retained in a SHA-verified full-tree backup; unknown changes are blocked, never silently removed.
- ZIP validation reuses existing protections, but the synthetic tests do NOT validate any actual future UEVR release assets, real Windows permissions, game-process locks, filesystem power-loss behavior, game-specific hooks, or headset playability.
- The two directory renames are serialized but not a single atomic replacement. The journal and verified displaced original support recovery after an interruption. Data remaining in a crashed fixture is deliberately short-lived and disposed at test completion; this is **not** a production rollback implementation.
- Every result retains \`authorized=False\`, \`live_executor_connected=False\` and \`real_game_compatibility_verified=False\`.

## Tests
- Focused profile staging + existing profile safety + K/L transaction regressions: **106/106 passed**.
- Final full regression discovery: **1,235 tests run, 1,234 passed, one skipped**, no failures.
- Final nine-game disposable KDE acceptance harness: **415/415 checks passed**.
- Actual subprocess exit occurred between moving the old profile and activating the new profile. A separate process verified it could recover the full original synthetic directory from the sealed journal and displaced tree.
- Additional simulated interruptions verified backup abort, staging, two rename points, post-commit rollback, rollback after rejecting the staged profile, and rollback after restoring the original. Fail-closed checks verified manual changed configs, unexpected user-added files, altered backup, modified permissions, corrupt journal, symlinks, stale source inputs, insufficient disk space, and complete original empty directories.
- Visually inspected Fatekeeper's rehearsal and synthetic safety-review KDE screenshots at 1630x1060. The existing five-column comparison stays usable; the preview-only control indicates both recovered test profiles, injector separation, real compatibility unknown and live updates blocked.
- Final KDE fixture and real-user preview storage checks show no mutation to the preview's saved state, scan history or custom folder preferences; the Nexus key is never copied.

## Desktop acceptance
1. Open the Dev5D3-O preview and confirm the existing archive-first scans and Nexus online Updates are intact. The two UEVR dependency entries remain separate (injector and profile).
2. Expand **Install / Update → Compare versions** and find \`Rehearse UEVR profile staging (TEST FIXTURE ONLY)\`; it should initially say **Not run**, not run automatically.
3. Click once and confirm **UEVR profile staging PASSED**, with Fatekeeper and Hogwarts Legacy each showing **whole directory restored**.
4. Confirm **2 synthetic profile rollbacks**, **configs and empty directories recovered**, **INJECTOR SEPARATE**, **REAL COMPATIBILITY UNVERIFIED** and **LIVE UPDATE DISABLED**.
5. Switching games clears the fixture result, and the comparison, safety review and preview-only rehearsal remain readable and scroll without overlap.
6. Installed integrity, manual archive controls, custom scan folders, KHARVOX tools, saved scans, backup/recovery and all existing live installer safeguards remain unchanged. No real profile, game, archive or Nexus key is written.

## Deferred
- Mapping verified real releases and compatible live injector builds; adopting/merging user-customized UEVR configurations; live whole-directory transactional backup/swap/recovery; permission models under Proton prefixes; game process exclusion; physical power-loss and filesystem crash consistency testing; live update authorization; VR gameplay verification; public release.
