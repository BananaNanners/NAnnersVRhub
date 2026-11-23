# Dev5D3-Q — Unified Update Planning & Safety Gate Consolidation

## Goal
Consolidate the Dev5D3-N/O/P pinned-package, UEVR whole-profile and Cyberpunk game-root update staging results into a single **read-only planning explanation** for all nine game profiles and 27 dependencies. Show safe next steps using the existing Review replacement safety control. No live update or restore execution, added production button or real file modifications.

## Facts observed
- Desktop-approved parent: Dev5D3-P commit b8abddaf703db7c314d7f1149b2d71e353272eb9, clean at fork.
- Existing downloads_gui.py already offers read-only Compare versions (local archives, installed provenance, separately refreshed online metadata) and explicit Review replacement safety (read-only), which generates preupdate_safety.review and update_integration.assess.
- The existing nine recipes describe 27 dependency rows across pinned BepInEx/ERVR, UEVR profiles/injectors, Cyberpunk Nexus game-root components and manual/guided workflows.
- Previously approved pinned_staging, uevr_profile_staging and cyberpunk_staging use invented ZIP bytes and disposable /tmp fixtures. They do NOT constitute verified real installation, game/runtime compatibility or live-update authorization.
- Safety and integration results already state authorized=False. Historical retained-original backups are not fresh pre-update backups, and no production transaction executor is connected.

## Proposed defaults
- Add vrhub/unified_update_plan.py as a pure non-executable adapter-neutral analyzer, receiving only the current game's existing read-only safety and integration dictionaries. Never import live installers, load state, access files, download or construct executable transactions in assess().
- Require exact recipe/game/unique component coverage, complete safety rows (excluding guide-only rows), safe authorized=False flags and known adapter types. Contradictory or cross-game evidence fails closed instead of reporting "ready".
- Present exactly three mutually exclusive advisory result codes: blocked (unsafe collision or all review evidence present but live execution disabled), needs_evidence (ownership, integrity, next archive, target mapping), manual (existing guided/injector workflow). A dangerous overlap takes priority over manual classification.
- Report four **observed review signals**, separately from six always-unresolved live gates: fresh backup; game stopped/exclusive lock; real compatibility/dependency order; real recovery strategy; separate game-specific approval; missing live executor. 4/4 observed means "Evidence reviewed — live replacement disabled", NEVER "safe to update".
- Give each dependency one concise recommended next review action. Keep its underlying detailed safety and adapter evidence in the existing scrollable review, not a new tab or persistent production button. The on-demand worker handles cancellation and game-switch invalidation as before.
- Expose a development-preview-only Rehearse unified update staging (TEST FIXTURE ONLY) control. It sequentially runs all six previously validated synthetic game rehearsals (three pinned, two UEVR, one Cyberpunk) and reports no live game access, preserved manual files, discarded temporary fixtures and real compatibility unverified.
- Continue preserving Downloads+custom game folder scans, separate online Nexus Updates, historical saved scans, installed integrity, KHARVOX tools, backup/rollback evidence and all overwrite safety gates.

## Decision needed
The user explicitly requested Dev5D3-Q after approving P. This offline/read-only implementation uses reversible defaults and requires no additional live action approval. **Real KDE desktop acceptance is still pending**, and no live-game update authority has been granted.

## Scope implemented
- New vrhub/unified_update_plan.py: schema-1 deterministic advisory report, strict component matching, safety-evidence priority and live gate refusals, pure 27-dependency normalization, six synthetic fixture family rehearsal adapter. No filesystem I/O in its analyzer.
- Updated vrhub/downloads_gui.py: the existing PreUpdateSafetyWorker attaches the non-executable unified result **after** completing its pre-update safety and adapter analysis; existing safety_details starts with UNIFIED UPDATE PLAN below the standard no-authorization warnings. Existing normal install controls, archive scanning, integrity and backup logic unchanged.
- New tests/test_unified_update_plan_q.py: 21 dedicated tests (all nine recipes, 27 components, manual/injector distinction, conflicting ownership, untracked file collision, target mismatch, cross-game and duplicate evidence, never-live authority, four observed review signals still blocked, no I/O or input mutation, fixture family rehearsals and actual Qt read-only review lifecycle).
- New tests/manual_launcher_dev5d3q_preview.py: inherits P's 9-game desktop verification and all prior protections; adds non-executable unified plan checks for every game, synthetic Fatekeeper 4/4 evidence still blocked, and a preview-only six-scenario staging/rollback exercise.

## Safety and rollback
- Isolated branch dev/0.5.5-unified-readonly-update-plan at ~/Projects/NAnnersVRhub-0.5.5-dev5d3q, forked from approved P b8abdda.
- Live game roots, Proton/Heroic prefixes, real UEVR profiles, user ZIPs, Nexus credential, user-owned state/scans/preferences, backups and historical Git worktrees remain untouched.
- Unified assess() never returns an authorization token, a destination path or an executable plan; every result sets authorized=False and live_executor_connected=False.
- All fixture demos use only invented files in disposable /tmp sandboxes and do not inspect or modify a selected game. Manual files and unrelated components stay protected.
- Returning to approved P is the source rollback path. Do not reset user data or rewrite historical commits.

## Tests
- Focused unified/integration/pre-update tests: 59/59 passed; initial test falsely assumed DOOM had a guide row, corrected to the actual KHARVOX manual component. Detected conflict now takes priority over a manual result.
- Full regression discovery: 1,288 tests run; **1,287 passed, one skipped**, no failures.
- Final isolated nine-game KDE harness: **428/428 checks passed**, including the synthetic Fatekeeper unified plan, all six synthetic staging/rollback cases, no install bypass, result reset on game switch, scroll layout and 27-component coverage.
- Visually inspected 1630×1060 Fatekeeper and Cyberpunk screens. Also directly captured the actual safety_details text widget showing UNIFIED UPDATE PLAN and explicit LIVE UPDATE DISABLED. Existing five-column comparison and button layout remain usable.
- Shared development preview state, archive scan history and per-game folder preferences retain their original SHA-256 digests, with source Nexus credential read-only and never copied.

## Desktop acceptance
1. Open the Dev5D3-Q preview; ordinary on-demand scanning of Downloads and the optional game folder and separate Nexus Updates remain available.
2. Expand Install / Update → Compare versions, then select Review replacement safety (read-only). The report now shows UNIFIED UPDATE PLAN near its top with a summary and clear per-dependency next review steps.
3. Check Fatekeeper/Hogwarts show injector/manual and profile as separate rows; Cyberpunk keeps its 15 components; BepInEx/ERVR and manual workflows are correctly distinguished. Even four observed review signals still read LIVE UPDATE DISABLED.
4. Click the **preview-only** Rehearse unified update staging (TEST FIXTURE ONLY). It reports three pinned game rehearsals, two UEVR whole-profile rehearsals, one Cyberpunk multi-component rehearsal and **six synthetic rollbacks**.
5. Confirm manual files preserved, temporary fixtures discarded, REAL COMPATIBILITY UNVERIFIED and LIVE UPDATE DISABLED. Switching games clears the synthetic result; detailed review scrolls without overlap.
6. Nexus online results, saved scans, integrity verification, manual ZIP review, KHARVOX tools, backups/recovery and all live install safety gates remain unchanged. No actual mod or game file is updated or restored.

## Deferred
Real release validation, exact compatibility with game builds and runtime, live process locks, fresh backups of installed mods, full production transactional executor/rollback validation, real filesystem power-loss cases, manually customized settings merging, user-authorized in-place update UI, VR headset/gameplay checks, public release.
