# Dev5D3-W — Cyberpunk Game-Root Archive Mapping & Conflict Validation

## Goal
Close the read-only Cyberpunk 2077 ZIP destination mapping gap. Strictly validate game-root ZIP member accounting and required component files, while keeping all installation, recovery, ownership-adoption and live updating disabled.

## Facts observed
- Approved parent Dev5D3-V: e2b5bd9135a11b016f5a92fdea386be44373befb; clean at fork.
- The original game-root installer supports at most one ZIP wrapper and canonicalizes top-level folder case, but can silently ignore documentation or other non-installable ZIP members. That is unacceptable for a complete update mapping claim.
- Cyberpunk has 15 Nexus components, with a required destination file specified for VR Port #30093. Component identification by archive filename is not a source authenticity check.
- Existing real update readiness is often blocked due to legacy installed-version and unverified source evidence, even when ZIP layout can be reviewed safely. W separates these read-only observations without changing readiness.
- Read-only spot-check of selected paths in an older saved Cyberpunk scan: 12 regular ZIP member inventories could be fully mapped, 2 were refused, and 1 selected file was not a ZIP. #18002 has unmapped regular members. The selected VR Port #30093 ZIP lacks its required payload in the expected location. Other saved matches, including three for VR Port, were not automatically selected as replacements.
- Example observed target counts: CET #107: 19, RED4ext #2380: 4, Input Loader #4575: 7. These are current metadata observations only, not certified release versions, actual game compatibility, or update permission.

## Proposed defaults
- A complete Cyberpunk mapping requires exact unambiguous recipe/Nexus component identity, strict ZIP preflight, all regular ZIP members mapped, required files present, valid relative targets, bounded member counts, safe wrapper handling, no casefold duplicates or file/directory ancestry conflicts.
- Keep extra unmapped files (including readmes), unsupported layouts, ambiguous candidates, missing required files, symlinks, traversal, stale selected paths, and unverified multiple archive choices blocked with clear sanitized reasons.
- A single unambiguous local Cyberpunk ZIP can undergo metadata mapping from the existing explicit Review replacement safety (read-only) action even while the independent online/update-readiness status remains blocked. Fresh SHA/size/stability are checked, but an unpinned filename is not authenticated Nexus provenance.
- Capture mapped targets transiently as cyberpunk_gameroot, feed existing V preservation/conflict audit, and show current ownership, source integrity, version/build compatibility, backups, recovery, and live execution as unresolved.
- Keep existing Controls, saved scans, Downloads plus custom folder behavior, separate Nexus online checking and six synthetic transaction rehearsals intact. Add only two accepted and four refused disposable synthetic ZIP layouts to the existing preview-only rehearsal; no production button.

## Decision needed
The user explicitly started Dev5D3-W after desktop approving V. Conservative read-only defaults are implemented. Actual KDE desktop acceptance is pending. No permission for any live mod changes, backups, repair, update, profile migration or ownership adoption was granted.

## Scope
- New vrhub/cyberpunk_archive_mapping.py: strict, metadata-only Cyberpunk ZIP member-to-target mapping based on existing safe preflight and game-root recipe rules, and a six-archive disposable synthetic rehearsal.
- vrhub/preupdate_safety.py: on explicit safety review, verify size, digest stability and archive identity, then map an unambiguous single Cyberpunk ZIP for layout-only review independently from update-readiness approval. Persist no target plans. Keep existing existing per-component refused statuses and backup gates.
- vrhub/destination_coverage.py: accept cyberpunk_gameroot provenance only for valid Cyberpunk components, and separately identify complete regular ZIP member accounting while leaving game/build and installed-file coverage unverified.
- vrhub/downloads_gui.py: readable, sanitized source-authentication and compatibility caveats for strict Cyberpunk maps in the existing review.
- New tests/test_cyberpunk_archive_mapping_w.py: valid direct/wrapped layouts, required VR Port payload, filename ID checks, unmapped docs, encrypted/symlink/traversal/duplicate/case/ancestor refusals, stale scans, untracked/manual-file conflicts, cross-component collisions, blocked update readiness with read-only mapping, no extraction/writes, and Qt review lifecycle.
- New tests/manual_launcher_dev5d3w_preview.py: inherits approved V nine-game KDE checks, adds a disposable mapping despite blocked readiness test and six invented ZIP parser cases in the existing fixture-only rehearsal.

## Safety/rollback
- Isolated worktree ~/Projects/NAnnersVRhub-0.5.5-dev5d3w on branch dev/0.5.5-cyberpunk-real-zip-mapping from approved V.
- Never extract ZIPs, hash installed mod contents as part of the mapping module, modify any game or archive, copy Nexus credentials, rewrite ownership/scan state, install mods, restore files or create backups. Synthetic ZIPs exist only in disposable /tmp folders.
- Current real observed mappings are based on selected files referenced by an older saved scan; do not infer newest release or absence of conflicting manual files from a metadata-only success. Regular ZIP member accounting does not authenticate or checksum every member's payload.
- All historical approved source checkpoints remain intact; rollback source to V without deleting any user data.

## Tests
- Final focused W/V/J suite: 88/88 passed.
- Full regression discovery: 1,456 tests run; 1,455 passed and 1 skipped, zero failures.
- Disposable nine-game KDE harness: 547/547 checks passed.
- Visual review: existing five-column comparison, read-only safety text and fixture-only result display stay readable without new production buttons.
- User preview state, archived scan snapshots and per-game custom folder settings retained their starting SHA-256 hashes; Nexus credential remains read-only and was not copied.

## Desktop acceptance
1. Dev5D3-W KDE preview opens with on-demand Downloads + custom game folder scan, saved scans, separate Nexus Updates and nine-game profiles intact.
2. Cyberpunk > Compare versions > Review replacement safety (read-only) can show game-root target counts for a safely mapped single archive even when update readiness remains blocked. Multiple ambiguous candidates and unsupported layouts remain unverified.
3. The Complete Destination Mapping & Preservation Coverage section labels strict Cyberpunk regular-file mapping without claiming authenticated Nexus release source, compatible game build or safe replacement. Missing required VR Port payloads and extra unmapped files are blocked with review reasons.
4. Manual/untracked files, conflicting component destinations, old Cyberpunk ownership and modified files remain review requirements; no auto-adoption, backup overwrite, repair, merge, or live installation is offered.
5. Existing Rehearse unified update staging (TEST FIXTURE ONLY) reports six synthetic rollback cases, six manifest scenarios, six complete synthetic target lists, two accepted Cyberpunk ZIP layouts, four blocked Cyberpunk ZIPs, two UEVR retirement holds and live updates disabled. Switching games clears the details.
6. Existing integrity check, KHARVOX controls, backups/recovery, archive review and installation safety gates remain intact; interface scrolls/readably fits without overlap.

## Deferred
Source-authenticated release hashes and newest archive identity; full ZIP member payload verification; handling readmes/optional files by deliberate policy; non-ZIP Cyberpunk archives; current installed ownership reconciliation; installed game/runtime compatibility; complete fresh backup, exclusive process lock and recovery; user-confirmed preservation; real update integration and headset/playtest approval.
