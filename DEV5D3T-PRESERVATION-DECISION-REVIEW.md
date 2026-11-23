# Dev5D3-T — Modified-File Preservation & Reconciliation Decision Planning

## Goal
Extend the approved S read-only ownership triage into a non-executable **modified-file preservation decision worksheet** that explains three possible review paths: preserve an existing modification, investigate an unknown difference, and consider a hypothetical future replacement. Keep changes inside the existing Verify installed files and Review replacement safety workflows. Do not enable a live update, adopt old ownership, mutate installed files, write backups, or change recorded SHA-256 hashes.

## Facts observed
- Desktop-approved parent: Dev5D3-S at commit `c41685d6a441aae70e17fe461280a64851c5717e` on a clean worktree. All prior dev checkpoints remain preserved.
- Read-only existing Hub results identify Valheim's `BepInEx/config/BepInEx.cfg` as Modified alongside two modified Unity/XR DLLs: `valheim_Data/Managed/UnityEngine.SpatialTracking.dll` and `valheim_Data/Managed/UnityEngine.XR.LegacyInputHelpers.dll`. Subnautica's `BepInEx/config/BepInEx.cfg` differs while the nine recorded Subnautica VR package files matched at the prior check.
- No evidence establishes whether these differences are intended, their exact mod release version, whether replacement would preserve gameplay, or whether a fresh restorable update backup exists.
- Legacy Cyberpunk component ownership and the Fatekeeper/Hogwarts UEVR profile evidence still have gaps; the earlier R and S reports are point-in-time read-only findings and must not silently upgrade to ownership authority.
- The existing read-only Review replacement safety control, R real-installation audit, S triage, and Q unified update plan already provide the correct place for an advisory worksheet. A new persistent selector or production update button is not needed in this milestone.

## Proposed defaults
- A changed configuration file receives a **recommended review path** `preserve_existing` by default. This is *advice*, not user approval and not an enforceable preservation rule. Changed binaries or non-config data receive `investigate_unknown`. Missing, unsafe and unverifiable files also require investigation before any action.
- `consider_future_replacement` is only a **session-only hypothetical draft review decision** for a reported Modified file within a component with established root-bound Hub ownership and the S `file_differences` classification. It is never a live replacement authorization, not evidence of candidate compatibility, and not an automatic download or restore.
- No explicit choices are gathered or saved by the production UI. The standalone model accepts optional in-memory explicit choices to prove future policy behavior and can show they were selected in that **test invocation only**. Without such input, recommendations are never misrepresented as user-confirmed decisions.
- Future choice inputs must match the exact game component and validated relative file name. Block missing/unsafe/unknown file replacement, unknown components, untracked files, duplicate/case-conflicting ownership, extra entries, unsafe paths, forged permission flags, and conflicting or partial evidence.
- The worksheet highlights the unchanged mandatory live gates: preserve current data, new verified whole-install backup, exact compatible release/target mapping, exclusive game lock and tested rollback, separate explicit user authorization, and disabled live executor.
- No file contents are read or hashed by the decision planner, and it cannot write any user/mod data, recorded hash, backup, state migration, or restoration instruction.
- Include only a concise summary and per-reported-file guidance inside the existing safety-details text widget; preserve all previous archive-first scanning, separate Nexus Updates, installed integrity verification, existing KHARVOX/manual tools, and six synthetic staging/rollback rehearsals.

## Decision needed
The user explicitly started implementation of Dev5D3-T after approving S. Conservative read-only, nonpersistent recommendations satisfy the milestone. **Manual KDE desktop acceptance is still pending.** Interactive user-selected policies, persistence, real protected-file merges and live update authorization require separate future design and approval.

## Scope
- New `vrhub/preservation_decisions.py`: pure, bounded, fail-closed worksheet model; three draft review paths; config vs binary recommendations; session-only optional explicit choices; strict per-file ownership and evidence checks; counts of unlisted differences; all actual-live gates unresolved and authorization always false.
- Updated `vrhub/downloads_gui.py`: after the existing user-initiated read-only safety review and S triage, attach the decision worksheet and display it in the same scrollable details. No new production tab/button and no change to installer, recovery, state-saving or archive scan logic.
- New `tests/test_preservation_decisions_t.py`: mock-only and Qt tests covering nine games/27 dependencies, Valheim and Subnautica scenarios, preserve/investigate/consider policy, missing/unsafe/unknown refusal, unowned component refusal, forged evidence, cross-game ambiguity, duplicate paths, insufficient bounded results, no I/O, no live updates, original GUI controls and game switch invalidation.
- New `tests/manual_launcher_dev5d3t_preview.py`: inherits approved S's nine-game desktop harness, adds 18 per-game preservation coverage/safety checks and synthetic Valheim and Fatekeeper review-path assertions, captures the worksheet text screen, and retains the six synthetic rollback rehearsals.

## Safety and rollback
- Isolated worktree `~/Projects/NAnnersVRhub-0.5.5-dev5d3t`, branch `dev/0.5.5-preservation-decision-planning`, forked from S `c41685d` without mutating the approved worktree.
- All model outputs have `live_update_authorized=False`, `real_backup_created=False`, `choices_saved=False`, `manual_files_adopted=False`, `recorded_file_hashes_rewritten=False`, and `real_compatibility_verified=False`.
- Current files are not protected by a connected live executor; the report explicitly says a preservation recommendation is not enforcement.
- Existing game roots, VR profiles, Proton prefixes, downloaded archives, real credentials, save files, historical backups, saved scan history and folder preferences are untouched.
- Rollback source to approved S; do not reset persistent Hub data or rewrite Git history. No real install, repair, backup, or restore occurred.

## Tests
- Focused T/S/R tests: **69/69 passed**.
- Full regression discovery: **1,357 tests run; 1,356 passed, one skipped**, zero failures.
- Final disposable nine-game KDE harness: **492/492 passed**. Synthetic test preview is isolated from live data; manual read-only review remains user-triggered and a game switch clears previous findings.
- Reviewed actual KDE 1630x1060 screenshots: existing Valheim integrity triage, the new worksheet's text viewport showing **Recommendations are NOT user decisions**, and the six-fixture staging review. Layout remains usable without extra production controls.
- Shared preview state, archived scan evidence and game folder preferences maintained their pre-development SHA-256 checksums during tests. Existing Nexus key remains read-only and is not copied.
- No actual file was modified or restored; compatibility and live update/backup recovery remain unverified.

## Desktop acceptance
1. Open Dev5D3-T preview. Saved on-demand Downloads + optional game folder scan and the separate Nexus online Updates continue to work.
2. In Valheim and Subnautica, use **Verify installed files** on demand. The BepInEx configuration differences remain tentative possible customizations, while Valheim's two Unity/XR DLL differences remain unknown binary drift—no attempted repair or overwrites.
3. Under Install / Update → Compare versions → **Review replacement safety (read-only)**, find **MODIFIED-FILE PRESERVATION DECISION WORKSHEET — READ ONLY** following S triage; recommendations clearly differ from explicit user choices.
4. The worksheet recommends preserving potential configuration customization and investigating unknown DLL changes, with `consider future replacement` clearly explained as review-only. It does NOT present a live replacement button or mark any current file as protected by an executor.
5. Cyberpunk legacy and UEVR profile/injector evidence stay unverified/manual where appropriate; historical matches and missing or unsafe files are never silently approved. No decisions, current hashes or ownership are saved or changed; switching games clears the old worksheet.
6. The six-scenario **TEST FIXTURE ONLY** rollback rehearsal, KHARVOX tools, archive inventory, backup/recovery and live installer refusal remain intact. GUI controls are readable, scrollable, and without overlap.

## Deferred
Persisted per-file user decisions, enforceable preservation or merge rules for real updates, exact future release compatibility, game process locks, fresh verified pre-update backups of actual mod trees, full live update and rollback, source-file changes requiring user approval, real headset validation, and publishing a public release.
