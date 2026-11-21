# NAnnersVRhub Dev5C2 — Cyberpunk persistent backups

Status: Implemented and offline-verified. KDE user approval is pending.
Branch: dev/0.5.5-cyberpunk-persistent-backups.
Baseline: approved Dev5C commit 81daacb.

## Why

Previously the game-root installer discarded original-file transaction backups
after successful installation, and legacy Cyberpunk inventory did not record
enough information for safe restoration. The generic legacy uninstall could
remove installed files without restoring overwritten originals.

## New installation contract

- Newly reviewed game-root installs are tagged installer=gameroot-2.
- Existing original files are SHA-256 verified, then retained in unique
  Hub-owned backups directories after successful installation.
- Installed-file hashes and each original's size/hash are recorded separately.
- Every selected archive passes bounded ZIP and destination checks before writes.
- Symlinks, unsafe destinations, overlapping targets, duplicate install records,
  and unsupported archive formats are blocked.
- The Hub still retains transaction backups through state commit, and can
  restore originals and remove new files after a failed transaction.
- Backups are kept after successful restore for optional manual recovery.

## Restore and rollback policy

- A new gameroot-2 record is required. No implicit migration of old installs.
- All installed files and original backups must exist, be regular files and
  match their recorded SHA-256 before the first restore operation.
- Missing files, user edits, tampering or symlink changes block the whole restore.
- Current installed bytes are staged before restoration. If state commit or
  restoration fails, the original installed bytes are restored.
- Recovery copies are retained if rollback fails and need manual inspection.
- Existing PAK and BepInEx installers retain their independent restore paths.

## The user's current Cyberpunk installation

- The existing saved Cyberpunk inventory is a legacy record without retained
  original-file backups. It remains untouched and automatic removal is blocked.
- The Downloads panel now displays a visible yellow LEGACY warning.
- The Uninstall confirmation refuses legacy restoration instead of pretending
  that originals can be safely recovered.
- The real read-only CET review finds 19 existing file replacements and
  blocks the operation because the legacy installation record exists.
- New installations without an earlier record can display persistent backup
  requirements, subject to the usual consent and stage-order checks.
- The later-stage CyberpunkVR Port remains a separate restricted step.

## Isolated development verification

- All game-write tests used temporary game folders, never the user's installed games.
- Tests cover preserved successful-install originals, correct restore, refusing
  modified installed files, bad or missing backups, legacy inventory protection,
  duplicate installs, failed original-copy publication, failed game writes,
  state-commit rollback, and symlink/destination safety.
- GUI tests verify legacy warnings and restore confirmation defaults to No.
- No real install, rollback or download was carried out.
- All nine saved archive scans remain in the persistent dev-preview store.
- The released Hub and previously approved development worktrees are unchanged.

## Desktop acceptance checklist

- [ ] Dev5C2 preview opens near 1630 x 1060 with the original theme.
- [ ] Cyberpunk Downloads / Install Plan shows the yellow LEGACY warning.
- [ ] CET's Review installation still lists 19 existing file conflicts.
- [ ] The displayed future backup policy is persistent originals with checksums.
- [ ] Existing legacy inventory blocks installation rather than offering false rollback.
- [ ] The preview Install button is disabled even when the checkboxes are checked.
- [ ] Original Mod Updates, artwork, library columns and VR System still function.
- [ ] Saved archive scans for all nine games remain available and retain timestamps.
- [ ] No live games, archives, mods, saves or production Hub state changed.
- [ ] User approves this review checkpoint before further work.

## Continuation

Legacy installations need a separate independently validated migration/recovery
strategy; bytes never saved previously cannot be reconstructed. Cyberpunk
successful-install backups and safe restore now have an offline-tested baseline.
Dev5C3 will address separate UEVR profile backups. Dev6 will address broader
per-mod rollback and backup management.

## Final verification — November 20, 2026

- Full Qt-offscreen suite: 865 tests run, 864 passed, 1 skipped.
- Isolated real-archive Qt preview: 92/92 GUI checks passed.
- Real Cyberpunk CET read-only check: 19 target replacements, legacy record
  correctly blocks replacement; persistent policy shown for new installations.
- Original Cyberpunk state and scanned CET archive were hash-unchanged.
- Nine saved game scan snapshots still persist in the shared dev-preview store.
- Additional guards refuse symlinked Hub backup roots and archives located
  inside the live game directory.
- No live Cyberpunk install, uninstall, restore or third-party download ran.
- This checkpoint is awaiting the user's real KDE visual acceptance.
