# Dev5D3-R — Real-Installation Readiness Audit & Safety Gap Assessment

## Goal
Audit **existing installation evidence** for all nine NAnnersVRhub game recipes (27 dependencies) using the Hub's read-only development-preview records, recipe-discovered installation locations, existing on-demand SHA verifier, and retained-original backup checks. Clearly distinguish a located game from Hub-managed ownership, historical hashes, real compatibility and the still-absent live update protocol. Keep the existing Review replacement safety button and do not authorize any real installer action.

## Facts observed
- Desktop-approved parent Dev5D3-Q: commit `ee5ee7acfa754bd820992a1e45557f99f4048f7b`, clean at fork. Live preview was running and all earlier checkpoints were preserved.
- Development-preview state and saved scan/folder preference files were SHA-256 inventoried before work. They are **not production update authorization records**. The R audit neither replaces nor migrates those records.
- Actual read-only per-game location / metadata observations:
  | Game | Preview state and discovered location | Evidence gap |
  |---|---|---|
  | Cyberpunk 2077 | Game directory found; 14 older Nexus component records, but no newer `gameroot-2` installed-file hash manifest | 15 current dependencies cannot be trusted for automatic replacement |
  | Valheim | Game directory found; two `vhvr-1` packages with file hashes | On-demand SHA check: 132/135 matched, 1 modified loader file and 2 modified VHVR files |
  | Subnautica | Game directory found; two `submersed-vr-1` package records | On-demand SHA check: 44/45 matched, 1 modified loader file; VR package 9/9 matched |
  | Elden Ring | `ervr-1` record exists, but Steam game location unresolved by the Hub locator | Recorded identity cannot be reconciled to a current root |
  | Fatekeeper | Game directory found; expected UEVR profile directory missing in the current derived prefix location; profile record exists without a complete installed SHA snapshot | Profile directory/ownership must be reconciled; injector remains separately manual |
  | Hogwarts Legacy | Game and expected profile directory found, but no full recorded installed profile SHA snapshot | Found directory is not trusted profile ownership; injector remains separately manual |
  | Ready or Not | Game directory found with legacy/manual state | No trusted automated-update inventory |
  | Skyrim VR MGO | Game directory found; guide/manual workflow | No trusted automated-update inventory |
  | DOOM (2016) | Game directory found; KHARVOX manual workflow | No trusted automated-update inventory |
- A **separate explicit read-only SHA-256 check** using existing `installed_integrity.verify` returned Unknown for components without valid manifests and Review for Valheim/Subnautica. **Four modified files in total** differ from recorded hashes, but that does NOT imply functional failure or establish what changed them. No file contents were exposed and no repair was performed.
- The existing read-only retained-original backup checker reported **Needs review** for all nine games *in the isolated development-preview context*. This does **not** prove production backups are absent or corrupted. Historical retained originals are not a new, full pre-update backup.
- No real new-release build compatibility, actual game process stop/lock, verified fresh backup/recovery plan or live update executor was available.
- The previous Dev5D3-N/O/P synthetic rehearsals remain useful but are not evidence that a real installed game can be updated safely.

## Proposed defaults
- Introduce a read-only point-in-time `real_readiness_audit.audit_game()` that accepts the existing user-triggered safety/integration state, observes only recipe-discovered **directory metadata** via `lstat`, and compares recorded ownership root identities as strings. It never reads game content, traverses untrusted state paths, persists changes or runs a repair. Any existing on-demand integrity result is described explicitly as a **prior check**, not as currently valid after the audit.
- Require complete, unique per-component integration records and false live-execution flags. Recheck recorded owner evidence against the provided Hub state without running another integration planner. Stale, forged or cross-game metadata must fail closed.
- Use consistent per-dependency audit outcomes: `blocked` for missing/unsafe/mismatched destinations, old hash mismatches or explicitly unsafe state; `needs_evidence` where ownership/integrity has not been established; `manual` for unsupported guided/injector workflows with located games. Missing real game location overrides the manual category.
- Six live safeguards always stay **unverified**: fresh complete verified backup, stopped game and exclusive update/restore lock, exact compatible new release, tested production rollback, separate explicit user approval and no enabled executor. No observation promotes a component to authorized.
- Reuse the existing **Review replacement safety (read-only)** action; append `REAL INSTALLATION READINESS AUDIT — READ ONLY / LIVE UPDATE DISABLED` within its current scrollable details, ahead of the Q unified plan and M integration contracts. No extra production buttons, tabs, automatic scans, or component adoption.
- The development preview retains Q's separate `Rehearse unified update staging (TEST FIXTURE ONLY)` action for six entirely synthetic cases. It is not a real game audit or repair.

## Decision needed
The user explicitly started Dev5D3-R after approving Q, specifying a read-only real-install readiness audit. This scope is conservative and reversible. **User KDE desktop acceptance is pending**. No user approval for any live game mutation, backup replacement, automatic update, real profile migration or release was granted.

## Scope implemented
- New `vrhub/real_readiness_audit.py`: per-recipe and all-nine-game read-only audit; directory location statuses, root-bound ownership, sanitized legacy record markers, prior-integrity distinctions, verified historical-original evidence distinction, explicit blockers, per-component next review steps and six never-authorized live gates. No file content reads or writes.
- Updated `vrhub/downloads_gui.py`: after the user initiates the existing pre-update safety review, the worker attaches a per-game audit report; the GUI renders its concise findings above the already approved Q/M sections. Existing install/restore controls and safety gates are unchanged. Review cancellation and game-switch invalidation remain in place.
- New `tests/test_real_readiness_audit_r.py`: test coverage for all nine games, 27 dependencies, no auto ownership adoption, valid/missing/symlinked/mismatched roots, malformed and forged state, manual UEVR injector separation, current-vs-prior integrity, old-vs-fresh backups, no unwanted file content reads or writes, no live installer invocation, and actual Qt GUI report lifecycle.
- New `tests/manual_launcher_dev5d3r_preview.py`: inherits the approved Q nine-game KDE harness with per-game real-audit no-authorization checks, synthetic Fatekeeper report for previous hash vs current proof, screen rendering and unchanged six-family fixture-only rollback control.
- No modifications to production installer APIs, game recipes, state-saving functions, backups, actual installed mods, Nexus credential, or existing historical tests.

## Safety / rollback
- Isolated worktree `~/Projects/NAnnersVRhub-0.5.5-dev5d3r`, branch `dev/0.5.5-real-install-readiness-audit`, based on Q commit `ee5ee7a`.
- Only recipe-derived directory metadata is directly inspected by R; it never treats a path from mutable state as permission to read that path. Explicit separate on-demand SHA verification and retained-original backup checks were performed **read-only** without copying hashes, file bytes, or credentials into Git.
- The new module returns `authorized=False`, `real_installer_connected=False`, `fresh_preupdate_backup=False`, `real_compatibility_verified=False`, and `production_recovery_verified=False` throughout.
- Current Dev5D3-N/O/P offline fixture engines remain disconnected from the real game roots; the synthetic rollback button is user-initiated and operates only on temporary fake games.
- No live game file, real mod ZIP, UEVR profile, Steam/Heroic prefix, user save, archived scan, custom folder, credential, backup, or existing Git history is changed.
- Rollback of source is the preserved, desktop-approved Q checkpoint; do not reset, overwrite or delete the user's persistent data. This is a **snapshot-style audit, not continuous monitoring**. Observations can become stale after any change.

## Tests
- Focused R/Q/M audit + GUI integration regression: **64/64 passed**. Initial failing test expected stale package ownership to remain trusted after a recorded root changed; corrected to explicit `blocked` root drift. Also corrected duplicated adapter-planner invocation without altering approved M/Q test expectations.
- Complete Hub regression suite: **1,313 run, 1,312 passed, 1 skipped**, zero failures.
- Final isolated nine-game KDE verification: **446/446 checks passed**. Covers 9 recipes / 27 dependencies, read-only report lifecycle, result invalidation on game change, no live authorization, original archive-first interface and preserved Q synthetic rehearsal.
- Visually inspected 1630×1060 Fatekeeper and Cyberpunk KDE preview screens and actual read-only safety-report text widget; the Real Installation Readiness Audit heading is visible, no overlapping buttons or columns.
- Shared development preview state, archive-scan history and custom folder preferences retained their initial SHA-256 digests. Nexus credential remains read-only and is never copied.

## Desktop acceptance
1. Open the Dev5D3-R KDE preview; saved scans, Downloads + custom game folder scanning, 15 Cyberpunk dependency rows, and separate Nexus Updates remain intact.
2. Expand Install / Update → Compare versions and click **Review replacement safety (read-only)**. The details include **REAL INSTALLATION READINESS AUDIT — READ ONLY / LIVE UPDATE DISABLED**, before the existing Unified update plan and adapter-contract sections.
3. Switch between Valheim/Subnautica, Fatekeeper/Hogwarts, Cyberpunk, Elden Ring and manual games: the audit distinguishes located directories, trusted Hub ownership, prior on-demand file hashes, manual workflows and missing/mismatched evidence without adopting files. A previous verified hash is never labelled current update permission.
4. Confirm retained-original backups are distinguished from the still-unverified **fresh pre-update backup**, with process lock, real compatibility, recovery and explicit approval all unresolved.
5. The preview-only **Rehearse unified update staging (TEST FIXTURE ONLY)** still reports six synthetic rollbacks, preserved manual files, temporary fixtures discarded, REAL COMPATIBILITY UNVERIFIED and LIVE UPDATE DISABLED. Switching games resets the synthetic result and clears prior safety review.
6. The interface remains readable and scrollable; installed-file integrity verification, archive selection, KHARVOX tools, Nexus updates, backups/recovery and all existing live-installation gates remain intact. No game/profile/backup modification occurs.

## Deferred
Verifying which modified file versions are intentional, safely reconciling old ownership records and current real game roots, adopting any manual install (never silently), verifying exact future Nexus/GitHub release contents, real game/build/Proton/UEVR compatibility, creating complete new verified pre-update backups, active process locking, real transactional update/rollback, power-loss recovery tests, actual VR/gameplay acceptance, opt-in live update authorization and release publication.
