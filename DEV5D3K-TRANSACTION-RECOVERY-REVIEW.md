# Dev5D3-K — Transactional Update & Recovery Architecture (offline only)

## Goal
Build and prove journaled, multi-file update and recovery behavior using disposable game fixtures only. No live installations or replacement authority.

## Facts observed
- Approved parent: Dev5D3-J commit b4e3f29d42f718a6a23d329228128d2ff5c95921 (clean at fork).
- Existing BepInEx/ERVR, game-root and UEVR profile installers refuse to overwrite an existing Hub-managed install. Their legacy original-file backups are not a fresh backup of current mods.
- Dev5D3-J already distinguishes historical backup evidence from a complete replacement/recovery plan. Multi-file update interruption requires an explicit durable journal and verified rollback.

## Proposed defaults
- Fixture-only module: create private owner-only temporary sandboxes under /tmp/nanners-dev5d3k-fixture-* with unique purpose/token marker. Accept synthetic bytes, never game paths, production recipes, mod ZIPs, or Hub state destinations.
- Build deterministic, fingerprinted old/new SHA-256 file manifests, tied to fixture ownership; reject stale plans, manual changes, path escapes, symlinks and case-insensitive collisions including untracked files.
- Enforce 64-file, 8 MiB-per-file and 64 MiB total bounds; preflight free space; preserve all owned fixture files via NEW and SHA-verified backups, including unchanged mods; stage and verify incoming payloads.
- Persist and fsync a sealed intent journal before any installed-file replacement. Use file-level atomic replace and a persistent recovery journal. Handle simulated interruptions after backup, during writes, before final commit and during rollback.
- On recovery, accept only original or known replacement hash for every owned file; verify backup content and journal seal; refuse to overwrite any unexpected manual modifications. Ordinary I/O errors cause automatic fixture rollback.
- Never surface a real update action, automatic repair, or live installer authority. The preview demo has an explicit TEST FIXTURE ONLY label and is reset on game switch.

## Decision needed
No blocker for the explicitly requested offline implementation. KDE desktop acceptance remains pending. Live update permission has NOT been granted.

## Scope
- New vrhub/offline_transaction.py: sandbox creation, deterministic plan, disk preflight, fresh backed-up staging, journal, fixture-only execute, simulated interrupts, recover, explicit committed rollback and status.
- New tests/test_offline_transaction_k.py: 23 focused test cases for success, multiple simulated crash points, cross-Python-process restart, automatic rollback after ordinary errors, stale plan, symlinks, case folding, changed manual files, backup/journal tampering, limits, cleanup and non-live paths.
- New tests/manual_launcher_dev5d3k_preview.py: inherits J desktop preview and adds a preview-only, manual click rehearsal section below Compare versions. No change to the approved production GUI source.
- Existing Dev5D3-J worktree and all historical checkpoints retained.

## Safety / rollback
- Isolated worktree at ~/Projects/NAnnersVRhub-0.5.5-dev5d3k on dev/0.5.5-transactional-offline-recovery.
- Roll back source by returning to approved Dev5D3-J b4e3f29. Never reset or delete user-owned scans, game files, backups or Nexus keys.
- Only disposable /tmp fixture data are modified. The source API does not accept real game, prefix, ZIP, install/rollback or archive paths. Preview live installations/transfers remain disabled.
- This is a test architecture, NOT a production transaction or an all-files atomic operation. During an interruption, an offline fixture can be temporarily partially updated until recovery completes.
- Empty parent folders created by a fixture addition can remain after rollback. Real-world concurrency, file/directory topology, power-loss durability across devices, disk I/O failures, recipe compatibility and headset behavior require separate work.

## Tests
- Focused transaction tests: 23/23 passed.
- Full regression: 1,138 total, 1,137 passed, 1 skipped, no failures.
- Final nine-game isolated KDE harness: 383/383 checks passed. The added controls do not overlap the J comparison section, are opt-in and cannot enable installs.
- Synthetic subprocess interruption and persisted-journal recovery successfully restored recorded bytes and removed the added fixture file.
- Preview state, archive scan history and per-game folder settings retained their original SHA-256 values. Original Nexus credential reused read-only, not copied.
- No live game or mod writes, downloads, extraction, rollback or backup mutation occurred.

## Desktop acceptance
1. Under Install / Update → Compare versions, see Rehearse interrupted update (TEST FIXTURE ONLY) with Not run initially.
2. Clicking it shows Fixture rollback PASSED, checked synthetic backup count, interrupted transaction recovered, fixture discarded and LIVE UPDATE DISABLED.
3. Switching games clears the previous fixture result; it must not represent a real game's integrity or update status.
4. The five-column version comparison, read-only safety review and fixture-only rehearsal scroll without overlap.
5. Nexus online Updates, local archive scanning, installed integrity, KHARVOX tools and previous backup/recovery gates remain unchanged.
6. No live installation, replacement, repair, recovery or game-file mutation is triggered.

## Deferred
Actual transactional upgrades for Hub-managed mods, fresh backups of real installed files, complete directory-tree rollback, real process locks and staging, disk-capacity reservation, user-facing update authorization, game/UEVR compatibility and VR gameplay validation.
