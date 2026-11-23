# Dev5D3-U — Preservation-Aware Update Manifest & Conflict Preview

## Goal
Provide a read-only before-and-after update preview that distinguishes hypothetical file additions, replacements, unchanged files, preservation holds, manual-file conflicts and proposed deletions. Use the existing safety review and preservation decisions without enabling any real file replacement or update.

## Facts observed
- Desktop-approved parent: Dev5D3-T, commit 4dfec5d241d8ef7aeeac7ba23cdc4e62d5bb243d. Parent worktree clean at fork.
- The approved T worksheet contains unsaved preservation recommendations, NOT confirmed user decisions or executable preservation rules.
- The existing real pre-update safety review contains bounded candidate destination samples and counts for some packages/profiles. These are NOT complete before-and-after real manifests, especially for legacy Cyberpunk components.
- The N/O/P fixture-only staging models can construct complete invented file inventories for Valheim, Subnautica, Elden Ring, Fatekeeper, Hogwarts Legacy and Cyberpunk 2077. Fixture compatibility is not real installation compatibility.
- Actual modified BepInEx config files and Valheim Unity/XR DLLs still require review. Their causes or correct future versions remain unknown.

## Proposed defaults
- Separate evidence tiers: real_readonly_samples never claims a complete real target map, while synthetic_complete is a full invented before-and-after comparison.
- Each synthetic destination is classified as add, replace, unchanged, preserve untouched, preservation hold, changed-owned hold, untracked collision, cross-component collision, case-only collision, file/directory collision or retirement hold. All classifications are descriptive.
- A T preservation recommendation or test-only explicit draft creates a hypothetical hold for candidate-overlapped files, even for consider future replacement. It does NOT become enforceable live protection.
- A proposed deletion of an old UEVR profile file is a retirement hold, not an instruction to delete. Current files omitted from candidates stay preserved.
- Reject unsafe paths, casefold duplicate file inventories, malformed SHA ownership, conflicting component attribution, unknown decisions, truncated/unsafe input and cross-game evidence. Candidate sample overlaps between components constitute a known conflict, even though no collision in the sample cannot certify full safety.
- Reuse Review replacement safety (read-only) in the production GUI; no new production button. Keep the existing preview-only fixture rehearsal button, but show six synthetic file-by-file manifests in one bounded read-only scrollable area.
- Always block real update permission, game installation writes, backup writes, restoration, ownership adoption and historical hash rewrites.

## Decision needed
The user explicitly started Dev5D3-U following desktop approval of T. Conservative non-executable defaults were implemented. Manual KDE desktop acceptance for U remains pending. No live mod update authorization has been given.

## Scope implemented
- New vrhub/update_manifest_preview.py: pure compare_fixture, preview_from_review and six-game synthetic demonstration. Validates source ownership, recorded hashes, file paths, policy holds, collisions and proposed retirement. Never creates an executable update plan.
- Modified vrhub/downloads_gui.py: on explicit read-only safety review, append PRESERVATION-AWARE UPDATE MANIFEST PREVIEW with incomplete real destination samples, current recorded counts, conflicts and next review steps. Preserve all existing controls.
- New tests/test_update_manifest_preview_u.py: correct fixture before/after actions; preserves customizations and untracked files; refuses stale, unsafe, conflicting, duplicate, forged, cross-game and live-authorized evidence; tests casefold and ancestor collisions, UEVR retirement holds and 27 dependencies across nine games; verifies no filesystem I/O or GUI update bypass.
- New tests/manual_launcher_dev5d3u_preview.py: extends the T nine-game KDE harness and adds test-only complete file-by-file manifests to the existing fixture rehearsal, with explicit before/candidate/hypothetical-after hash prefixes in a scrollable read-only field. Shows six synthetic update-and-rollback scenarios across three staging families.

## Safety and rollback
- Isolated branch dev/0.5.5-preservation-aware-manifest, worktree ~/Projects/NAnnersVRhub-0.5.5-dev5d3u, based on approved T commit 4dfec5d.
- Real game files, mod ZIPs, Steam/Heroic prefixes, saves, profiles, Nexus credential, backup inventories, persistent state, archived scans, custom folder preferences and prior Git checkpoints are preserved.
- Synthetic fixtures contain invented bytes, not user game files. Comparison itself performs no I/O; staging rehearsals operate only in their existing private temporary fixture trees.
- A hypothetical after-state is not an actual disk state. Known overlap on sampled real candidate targets is a conflict hint, not a full collision inventory. All real compatibility, fresh backup, process locking, full real recovery and explicit live permission remain unverified.
- Source rollback path: return to approved T worktree/commit without resetting user-owned data.

## Tests
- Focused U/T/S tests: 75/75 passing.
- Full test discovery: 1,388 run; 1,387 passed and one skipped; no failures.
- Disposable nine-game KDE harness: 519/519 checks passed.
- Screenshots visually checked: original archive/version comparison layout, real incomplete manifest section within the safety report, synthetic before/after file detail area, original integrity triage. No new production button or overlapping controls.
- Six fixture manifests include three pinned-package games, two UEVR profiles and Cyberpunk. Two UEVR retirement proposals are held. Untracked/manual files remain untouched in the hypothetical state. The existing six synthetic rollback tests still pass.
- Original preview state, scan snapshots and custom folder preferences retained their starting SHA-256 hashes. Nexus credential remains read-only and is not copied.

## Desktop acceptance
1. Open U preview and check archive-first on-demand Downloads + optional custom game folder scanning, saved scans, separate Nexus Updates, and all nine game profiles.
2. Under Install / Update > Compare versions > Review replacement safety (read-only), find PRESERVATION-AWARE UPDATE MANIFEST PREVIEW. Confirm the real BEFORE is recorded counts only, and AFTER is partial candidate samples; no complete real update is claimed.
3. Confirm configured-file recommendations, unresolved Valheim DLLs, Cyberpunk legacy component uncertainty and UEVR profile/injector distinctions remain guarded. No automatic overwrite, hash rewrite, adoption or real compatibility claim.
4. Click existing Rehearse unified update staging (TEST FIXTURE ONLY). Confirm six synthetic rollbacks, six synthetic before/after manifests, two UEVR retirement holds, manual files preserved, REAL COMPATIBILITY UNVERIFIED and LIVE UPDATE DISABLED.
5. Inspect the read-only file-by-file TEST FIXTURE ONLY detail field: BEFORE/CANDIDATE/HYPOTHETICAL AFTER, add/replace/untouched actions and UEVR retirement holds. Selecting another game clears both the fixture result and stale read-only review.
6. Confirm original integrity verification, KHARVOX specialist actions, backup/recovery, archive selection, installation safety gates and GUI readability remain intact with no new live installation actions.

## Deferred
Complete real archive-to-destination manifests and attribution for all mod families; proof of actual game/runtime compatibility; confirmation of intentional modifications and safe merges; verified fresh backup and process exclusion; real transactional rollback and power-loss recovery; persistent user-confirmed protection policies; live updating after separate authorization; VR gameplay verification and release publication.
