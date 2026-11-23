# Dev5D3-L — Transaction Recovery Hardening & Rehearsal Coverage

## Goal
Harden the approved Dev5D3-K fixture-only transaction engine so interrupted backup creation, stale ownership evidence, interrupted rollback, and incomplete directory restoration are handled conservatively. Prove behavior using disposable game trees and process-kill rehearsals, never real Steam, Heroic, or UEVR installations.

## Facts observed
- Approved Dev5D3-K parent checkpoint: 328282c8677b1242b9b72873652790caf525a456. The parent worktree was clean. All historical worktrees and user-owned preview state remain protected.
- K first persisted its recovery journal after all backups and staged payloads were copied. An interruption during preparation could leave unjournaled partial copies.
- K restored managed file bytes but could leave transaction-created empty directory ancestors behind, and replacement did not preserve original file permissions.
- K had an unsealed ownership inventory. Its journal was sealed, but recovery should also reject changed or stale ownership evidence.
- Existing live installers deliberately refuse to overwrite a Hub-managed installation. This restriction remains in effect.

## Proposed defaults
- Persist a sealed preparing journal BEFORE the first backup or staged copy. If preparation is interrupted, verify the installed fixture is unchanged and mark the partial backup as untrusted and aborted_before_apply; do not resume an incomplete copy as if it were verified.
- Record all installed fixture directories including empty ones, directory permissions, and owned file modes. Bind those records into the plan fingerprint and journal.
- Before rollback, reject changed ownership, unexpected files and directories, altered permissions, missing or modified files, and unsafe paths. Restore managed files and remove only transaction-created EMPTY directories, deepest first, preserving all manual changes.
- Seal fixture ownership inventory. Support before-commit and after-commit inventory states during recovery without accepting arbitrary changes.
- Keep the engine fixture-only under protected /tmp/nanners-dev5d3k-fixture-* sandboxes. Use synthetic bytes, path and size bounds, no symlinks, no direct production connection.
- Test abrupt process exit during backup and during file update before journal progress, plus re-entry during directory cleanup and manual-edit protection.
- Add a Dev5D3-L development-preview-only Rehearse hardened recovery (TEST FIXTURE ONLY) button below the already-approved Compare versions layout. Demonstrate safe abort, full directory cleanup and manual edit preservation. Clear its synthetic outcome on game switch.

## Decision needed
The user explicitly requested Dev5D3-L offline-only development. No further blocker for a conservative fixture implementation. Actual KDE desktop acceptance is still pending. No live game modification authority is granted.

## Scope
- vrhub/offline_transaction.py: preparing/aborted phases, sealed ownership, directory and file mode manifests, conservative recovery preflight, full directory restoration, crash/resume fault injection and demo_hardened.
- tests/test_offline_transaction_l.py: 19 additional focused failure-path tests, including separate subprocess os._exit during backup and after file update before progress logging.
- tests/manual_launcher_dev5d3l_preview.py: nine-game isolated KDE harness with new fixture-only recovery demonstration. Existing production downloads_gui.py is unchanged.
- All historical Git checkpoints, approved K test behaviors and live installation safety gates are preserved.

## Safety / rollback
- Isolated worktree ~/Projects/NAnnersVRhub-0.5.5-dev5d3l, branch dev/0.5.5-recovery-hardening, based on approved K commit 328282c. Roll back source to K without changing preview state or backups.
- No game files, Steam or Heroic prefixes, real mod ZIPs, UEVR profiles, Nexus credential, saved archive scans, backup history or recovery records are modified.
- Fixture process termination is exercised with real subprocess os._exit, NOT a physical power-loss test. The fixture journal does not provide production-grade all-files atomic updates.
- Original permissions and empty directories are restored in fixtures. Unexpected manual files and directories block rollback rather than being removed.
- Incomplete backups remain explicitly UNTRUSTED and are discarded with the disposable temporary fixture. No live repair, download, update or rollback becomes enabled.

## Tests
- K transaction tests: 23/23 passed.
- L transaction tests: 19/19 passed; combined 42/42.
- Full regression: 1,157 tests run; 1,156 passed and 1 skipped; zero failures.
- Final nine-game KDE harness: 386/386 checks passed. Demonstrates initial not-run, user-triggered fixture rollback, incomplete backup safe abort, two created directories removed, manual edits preserved, result reset on game switch, unchanged installer gates and scroll layout.
- Screenshot visually inspected at 1630×1060 for the Valheim test-fixture demonstration; no controls overlap.
- User-owned development preview state, scan history and folder preferences are preserved; reverify hashes after opening desktop preview.

## Desktop acceptance
1. Compare versions shows Rehearse hardened recovery (TEST FIXTURE ONLY); initially not run.
2. Click rehearsal; see Hardened fixture recovery PASSED, incomplete backup safely aborted, 2 created directories removed, manual changes preserved, LIVE UPDATE DISABLED.
3. Switching games clears the demonstration result; it never implies real installed game status.
4. Version comparison, safety review and rehearsal controls remain readable and scroll cleanly.
5. Nexus Updates, archive scanning, installed integrity, KHARVOX tools, manual review, backups and recovery continue unchanged.
6. No real game or mod files are modified and no live installer, restore or update is enabled.

## Deferred
Connecting transactions to real installations; full real UEVR profile snapshots and restore; exclusive game-process locking; physical power-failure tests; malicious local process threat model; production dependency and compatibility planning; real disk space reservation; VR headset/gameplay validation and release publication.
