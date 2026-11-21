# NAnnersVRhub 0.5.5-dev5C3 — UEVR Profile Backup and Recovery

Status: **offline implementation complete; KDE desktop acceptance pending**.

Approved base: Dev5C2 commit f621e1a.
Branch: dev/0.5.5-uevr-profile-backups.
Worktree: ~/Projects/NAnnersVRhub-0.5.5-dev5c3.

## Approved Phase 1 requirements

1. Before any UEVR profile replacement, create and verify a **persistent,
   complete backup** of the existing profile directory, including previously
   untracked files, nested directories and empty directories. Require explicit
   destination and backup-policy confirmation.
2. Treat all current profile contents as **user-owned**. Never silently adopt
   existing Hub legacy records or replace missing/inconsistent profile
   directories. Fatekeeper and Hogwarts Legacy have existing legacy records
   and remain blocked pending a separate recovery review.
3. Before restoring, verify every installed file and directory and the retained
   original backup. Reject any addition, removal, or modification. Never
   silently overwrite post-install user customizations.

## Implemented in the isolated worktree

- vrhub/profile_safety.py: read-only inventory, review fingerprint, bounded ZIP
  preflight, path/symlink/case-collision checks, persistent whole-directory
  backups, staged replacement and restore, checksum-based drift rejection,
  and rollback of failed state saves. Original backups survive restoration.
- ZIP and current profile are reverified immediately before replacement.
  Installed profile is reverified immediately before restoration.
- Recognized active game processes are blocked; real-game detection still needs
  independent verification before production enablement.
- The Hub and CLI require explicit confirmation and a matching review
  fingerprint. Legacy profile inventories never fall through to generic
  destructive uninstall behavior.
- vrhub/profile_review_gui.py shows exact destination, archived file inventory,
  existing file and directory counts, and full-backup and legacy warnings.
- GUI profile installation is a read-only review in Dev5C3. Profile restores
  require a clean preflight and separate explicit confirmation.
- New tests cover successful install/restore, existing/untracked files, empty
  directories, modified/missing/added files, corrupt original backups, stale
  plans, stage-time user edits, unsafe ZIPs and symlinks, legacy records,
  failed state writes and rollback, game-running checks and GUI confirmation.
- tests/manual_launcher_dev5c3_preview.py is an independent, read-only Qt
  preview, preserving existing nine-game saved archive scans.

## MECHANICAL LIVE-EXECUTION SAFETY GATE — CLOSED

The execution gate rejects ALL live UEVR profile install and restore calls,
even if a caller presents a confirmation fingerprint. Tests bypass this gate
ONLY for isolated disposable fixture directories. The production Hub and
existing Fatekeeper/Hogwarts/Cyberpunk installations remain unchanged.

This is NOT a release or live-install approval. A separate explicit user
authorization, process-safety validation and on-device acceptance are required
before enabling real UEVR profile writes.

## Known legacy profile states (read-only)

- Fatekeeper: 95 profile files tracked, expected profile directory absent,
  retained older backup contains 88 files. No migration or restore attempted.
- Hogwarts Legacy: 193 actual files, 19 subdirectories, approximately 54.5 MB.
  Legacy state tracks 192 files. The untracked file is protected as user data.
- Neither legacy record has been migrated to the profile-2 format.

## Deferred safety work

- Investigate legacy record reconciliation and manual recovery separately.
- Validate game-running detection under actual Proton/Heroic sessions.
- Review process-crash recovery and shared Hub state-write concurrency before
  releasing production install or restore code.
- Do not weaken approved Dev5C2 Cyberpunk guards.
- Do not treat offline tests or KDE preview as headset/gameplay validation.

## Desktop acceptance checklist

- [ ] Open 0.5.5-dev5C3 KDE PREVIEW at normal launcher size.
- [ ] Select Hogwarts Legacy and expand Advanced Tools.
- [ ] Click Review UEVR profile… and choose a local profile ZIP.
- [ ] Confirm exact destination, archive files, current inventory, full backup
      policy and original retention appear in the review.
- [ ] Existing legacy record shows a BLOCKED manual recovery warning. Apply
      remains disabled even after checking the acknowledgement.
- [ ] Read-only synthetic review says READ-ONLY PREVIEW — INSTALLATION IS
      DISABLED; it does not pretend a real install is authorized.
- [ ] Original game library, updates, VR System and saved archive scans work.
- [ ] Real game installations, Proton/Heroic prefixes, downloads, saves, Hub
      production state, and Dev5C2 approved baseline remain unchanged.
- [ ] User explicitly accepts the KDE visual result.

## Verification

Final verification: **896 automated tests, 895 passed, 1 skipped**.
Fresh isolated native Qt preview: **97/97 checks passed**.
Nine historical game archive scans remain in the private development store.
All checks use disposable fixtures or read-only game inspection. No live UEVR
profile install/uninstall/restore or VR gameplay test has been run.
Checkpoint commit and desktop preview PID are recorded separately.

**Do not enable UEVR profile live execution from this checkpoint alone.**
