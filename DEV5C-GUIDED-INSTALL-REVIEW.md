# NAnnersVRhub 0.5.5-dev5C — Guided Installation & Safety Confirmations

Status: First Dev5C guided-install checkpoint implemented; KDE acceptance pending.
Approved baseline: Dev5B2 commit 8e1670c.
Branch: dev/0.5.5-guided-installs.
Worktree: ~/Projects/NAnnersVRhub-0.5.5-dev5c.

## Why this milestone matters

An archive found locally is not authorization to install it. Before any
supported mod installation, show the *exact planned destination files*,
the original-file backup and conflict policy, and require deliberate
user confirmation. Never claim gameplay or VR readiness merely because
an archive and its files exist.

## Guided review flow

1. Downloads / Install Plan now includes **Review installation**.
2. The older installer action is relabeled **Review mod archives**, and it
   runs the SAME review workflow before any installer can be invoked.
3. The selected archive is validated read-only against the current recipe,
   storefront game folder, exact destination paths, installer requirements
   and backed-up originals. Saved scan results do not replace this review.
4. The review dialog shows game directory, package names, exact file list,
   add/replace action, existing sizes, backup policy and blockers.
5. Three separate acknowledgments are required: destinations reviewed;
   understood backup policy; game closed and this installation authorized.
6. **Install reviewed archives** remains disabled until all three are
   selected and the current manifest has no safety blockers.
7. Immediately after confirmation the planner rehashes the selected
   archives and existing files, and compares a signed manifest fingerprint.
   If anything changed, install is aborted before any game modification.
8. Only supported and confirmed operations call the existing transactional
   Hub installer. Cancelling or closing the review makes no changes.
9. The isolated Dev5C preview has the additional enforced no-install
   switch, even if an approval dialog were accidentally accepted.

## Supported installer safety policies

### Valheim, Subnautica and Elden Ring

Pinned VR package ZIPs must pass exact SHA-256 and required-file checks.
All required packages must be selected together. The existing
BepInEx/ERVR installer retains backups of original game files and
supports transactional rollback. Current Hub-managed install records,
incompatible plugins, unsafe symlinks, case collisions and insufficient
backup space block a new installation.

### Ready or Not / PAK

Only one explicit PAK or ZIP containing PAK payloads is supported.
Duplicate basenames, unsafe destinations, invalid ZIPs and symlinks
are refused. The existing PAK installer retains original backups and
has failure recovery. A prior installation record blocks replacement.

### Cyberpunk game-root packages

ZIPs are bounded and inspected for traversal, unsafe entry types,
duplicates, encryption and excessive expanded size before staging.
Each component must be matched to the proper Nexus mod number and
satisfy required destination sentinels.

Only stage-1 packages that add NEW files can be candidates.
Replacement of an existing game file is **blocked** because this
existing game-root installer only keeps failure-time backups; it does
not retain originals after a successful installation. The CyberpunkVR
Port's stage-2 install stays blocked pending first-flat-launch and
prerequisite confirmation.

### UEVR profile and unsupported guide-only workflows

UEVR profile installation is explicitly on a safety hold in this
development branch. The older profile route can no longer skip review
and overwrite a profile without the separately validated folder
backup/rollback procedure. Users can still read Setup guide directions.
No promise of one-click install for these unsupported cases is made.

## Real-data read-only test

Using existing local VR-Mods archives and an isolated copy of Hub state:

- Cyberpunk 2077 CET would replace 19 existing game files. The
  guided planner correctly BLOCKED that installation.
- Valheim and Subnautica have recorded Hub installations. A second
  install was refused without replacing those records.
- Elden Ring was not detected, so installation was refused.
- The isolated Hub state checksum did not change.
- No archives, mods, Steam/Heroic settings, saves or game files were
  modified by those inspections.

The new KDE review dialog was also tested with a clearly marked
synthetic game and sample destination. It never invokes a real installer.

## Test isolation

The Dev5C review window points to the separate test state under
~/.cache/nannersvrhub-055-dev5c-state-20261120/ with isolated XDG
settings. Both allow_guided_installs and allow_transfers are disabled.
Existing game launch, uninstall, Hub self-update and other mutating
actions remain disabled in the preview.

This milestone does not yet include live-game installation testing.
The released Hub 0.5.4 and all approved Dev1–Dev5B2 worktrees remain
unchanged. Manual KDE acceptance is still required.

## Dev5C KDE acceptance checklist

- [ ] Window opens near 1630 x 1060 with approved branding and layout.
- [ ] Downloads / Install Plan includes Review installation.
- [ ] Cyberpunk CET is preselected; click Review installation and
      inspect its real blocked existing-file overwrite preview.
- [ ] Review shows game path, exact file destinations and new versus
      replacement counts.
- [ ] Backup and conflict policies are clearly stated.
- [ ] Review table is scrollable; columns can be resized.
- [ ] All three user acknowledgments and Cancel are present.
- [ ] Install reviewed archives stays disabled in the isolated preview
      even after every acknowledgment is checked.
- [ ] The old action now says Review mod archives.
- [ ] UEVR profile installation remains on an explicit safety hold.
- [ ] Cyberpunk stage-2 VR Port remains blocked until separate checks.
- [ ] Prior scans, artwork, Mod Updates, column resizing and VR System
      still function.
- [ ] No game, mod, save, archive, or production Hub files were changed.
- [ ] User approves this checkpoint before subsequent Dev5C work.

## Continuation

A future Dev5C stage must independently validate successful-install
backup retention for Cyberpunk replacements, and profile-dir recovery
for UEVR. Dev6 remains focused on per-mod rollback management.

## Verified checkpoint — November 20, 2026

- Complete Qt-offscreen regression: **824 tests, 823 passed, 1 skipped**.
- Isolated real-data Qt preview: **88/88 checks passed**.
- The sample review dialog explicitly says PREVIEW ONLY. Its Apply button
  remains disabled even after checking all three consent boxes.
- Actual Cyberpunk CET archive inspection is read-only; 19 file replacements
  correctly trigger the persistent-backup block. Previously installed
  Valheim/Subnautica also refuse duplicate inventory installation.
- The old install route and the new Downloads tab share the same planning,
  approval, and fresh-hash-revalidation gates.
- The developer preview permits review but has allow_guided_installs=False,
  allow_transfers=False, and disabled game launch/rollback/Hub update actions.
- No live installer was run; this is NOT a live-install certification.
- User KDE desktop acceptance remains pending.
