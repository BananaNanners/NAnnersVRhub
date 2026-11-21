# NAnnersVRhub 0.5.5-dev5D2 — Archive-First Installation Interface

Status: implemented, offline verification passed; KDE desktop acceptance pending.
Approved base: b124b30 (Dev5D1-C). Branch: dev/0.5.5-archive-first.

## Changes
- Install / Update starts with an archive dependency checklist, with the downloaded archive column first. Existing logical column identities and saved widths remain intact.
- One row per declared dependency, showing the selected archive candidate or missing result. No internal archive entries in this checklist.
- Green check: recipe-pinned SHA-256 matched in the scan. Yellow: filename-only candidate. Red: mismatched, unchecked required hash, or changed archive. Grey: missing/not checked. History is not a fresh verification or installation authority.
- Current recipe requirements are compared with historical scan rows. A changed dependency definition/pin requires a rescan, without deleting the historical record.
- Archive hover shows exact path, human-readable size and, where applicable, matching-candidate count.
- Complete distinct pinned BepInEx/ERVR sets display "Review N verified archives" and use the existing package-set review request. No automatic installation or new bulk installer path.
- Individual archive inspection remains available under More installation tools.
- Archive review displays selected archive filenames, recorded SHA-256 review evidence (not a claim of pinned verification), destination, counts, backup policy and blockers. Exact destination-file manifest collapses by default.
- Profile review shows its archive, destination, file counts and whole-directory backup estimate. Full profile inventory is collapsed by default.
- Both dialogs retain all existing consent requirements. Opening the complete manifest once is required before acknowledging it. No individual file selections are required. Blockers cannot be overridden.

## Preservation
- No changes to the underlying archive scanner, snapshot serializer, install plan builder, installer, download verifier, game handlers or profile safety engine.
- Existing stage ordering, exact destination checks, package requirements, conflict checks, manifest fingerprint revalidation, original-file backup and recovery policies remain intact.
- Live UEVR profile replacement remains mechanically disabled.
- No game archives, installed mods, game files or production Hub files changed.
- Eight historical game scan records were present before this work; their shared snapshot hash remained unchanged. Earlier one/nine-count reports are not evidence of deletion or recovery. The isolated verification copy acquired nine records by running the existing read-only scan tests. Never copy those verification results back into the shared store.
- Shared state, snapshot and download-folder preference hashes match pre-development values.

## Verification
- Full regression suite: 939 run, 938 passed, 1 skipped.
- Isolated Qt preview: 177/177 checks passed.
- Eight new archive-first tests cover column order, pinned complete-set request, mismatched recipe pins, candidate/changed results, status icon semantics, archive summary and complete expandable manifest, blockers, and profile preview gating.
- Read-only synthetic dialog previews plus real archived dependency results were rendered for visual inspection.

## Desktop acceptance
1. Install / Update shows archive filenames first, one row per dependency, with no internal archive contents.
2. Subnautica shows its two pinned archives with green checks and Review 2 verified archives (when the saved results remain current).
3. Cyberpunk filename-only results are yellow, legacy backup warning and later-stage labels retained.
4. Other games display their appropriate results, sources and shared/per-game folders. Switching games retains saved scan history.
5. Review selected archives shows archive names, exact destination, backup policy, review evidence; Show exact file changes opens complete manifest.
6. UEVR profile review starts collapsed, preserves whole-directory backup summary, and can expand full inventory.
7. More installation tools exposes the existing optional inspector; table columns remain resizable.
8. Live-changing actions remain disabled in the read-only desktop preview.

Dev5D2 desktop approval is a presentation/workflow approval only, not authorization to enable real installation or UEVR profile execution.
