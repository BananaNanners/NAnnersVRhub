# Dev5D3-V — Complete Destination Mapping & Preservation Coverage Audit

## Goal
Audit verified ZIP-to-install-target coverage and preservation conflicts without changing installed games or authorizing real updates. Keep the existing archive-first interface and strictly distinguish complete recipe target lists from full ZIP membership, full installed ownership, game compatibility, or recovery approval.

## Facts observed
- Approved parent: Dev5D3-U, commit fd9b58d7569a1066cf6377af63761529a71bfa6e, clean at fork.
- The existing pre-update safety parser rehashes a candidate ZIP, then can enumerate the recipe-mapped installation targets of pinned BepInEx packages and UEVR profiles. Previously only a short destination sample/count survived in the result. For pinned packages, selected metadata/readme files may be intentionally excluded: a target list is not a complete ZIP member inventory.
- Real Cyberpunk game-root component updates remain unsupported in the verified on-demand target mapper. U's existing real manifest is a sampled advisory view, not a safe update or complete current installed-file snapshot.
- T's preservation choices are recommendations, not saved or enforced protections. Valheim/Subnautica modified files and UEVR ownership gaps remain unresolved.

## Proposed defaults
- Retain the full bounded mapped target list only in the transient read-only pre-update safety result, with parser provenance for pinned packages or UEVR profiles. Never treat it as an executable update plan or persist it to Hub state.
- Reconcile target counts with samples, validate safe relative paths, refuse case-insensitive duplicates and parent/child file collisions, and detect positive full-list overlaps between mapped components.
- Match recorded preservation issue paths against complete candidate target paths. Report both overlapping modified files and changed files outside known targets as requiring review.
- Keep real destination mapping unknown whenever a candidate ZIP or supported parser is missing. Complete mapped target lists remain only point-in-time, recipe-scoped evidence and never establish complete ZIP coverage, current installed ownership, compatibility, user consent or safe replacement.
- Reuse the existing Review replacement safety (read-only) area and preview-only rehearsal control. Do not introduce a production button or live executor.
- Preserve all previous archive-first scanning, separate Nexus Updates, integrity, KHARVOX, recovery and six-fixture staging safeguards.

## Decision needed
The user explicitly started Dev5D3-V after desktop acceptance of U. This conservative read-only development is implemented; manual KDE desktop acceptance remains pending. Live updating and real file preservation require separate authority.

## Scope
- vrhub/preupdate_safety.py: add ephemeral bounded full_target_list and full_target_provenance after existing read-only candidate verification; preserve the old displayed sample.
- vrhub/destination_coverage.py: pure, fail-closed destination and preservation overlap audit. Reuse U's validated manifest within the review worker instead of invoking it twice. Never touch real file contents.
- vrhub/downloads_gui.py: append COMPLETE DESTINATION MAPPING & PRESERVATION COVERAGE — READ ONLY to the existing safety report, with per-dependency mapping scope, counts, overlap hints and next steps.
- tests/test_destination_coverage_v.py: 9-game/27-component inventory, pinned and UEVR target mapping, Cyberpunk unsupported real mapping, malformed/unsafe path refusal, cross-component collisions, modified-file preservation, no file writes, and Qt review/reset tests.
- tests/manual_launcher_dev5d3v_preview.py: inherit U desktop coverage, add read-only mapping checks and a synthetic Fatekeeper two-target profile test. Existing six synthetic rollbacks and six manifest comparisons remain present.

## Safety / rollback
- Isolated worktree ~/Projects/NAnnersVRhub-0.5.5-dev5d3v, branch dev/0.5.5-destination-coverage-audit, forked from approved U commit fd9b58d.
- Actual game roots, downloaded ZIPs, Steam/Heroic prefixes, UEVR profiles, credentials, backups, user saves, archived scan history, folder preferences and recorded SHA values remain unchanged.
- Temporary synthetic staging fixtures are invented and disposable; the new audit is pure and never constructs executable operations. Real source candidates, if reviewed, are read by the existing explicit read-only ZIP parser.
- Return to approved U to roll back source without resetting or deleting user data, backups or Git history.

## Tests
- Focused V/U/pre-update tests: 72/72 passed. Initially duplicated U validation was corrected to reuse the existing validated report. Synthetic preservation test filename was aligned with its worksheet.
- Full Hub regression suite: 1,409 run, 1,408 passed and one skipped, no failures.
- Isolated nine-game KDE harness: 540/540 checks passed.
- Visually inspected screenshots of the new read-only coverage summary and synthetic per-file view; no extra production controls or overlap.
- Shared preview state, scan snapshots and game-folder preferences retained original SHA-256 checksums; Nexus key is not copied.

## Desktop acceptance
1. Open Dev5D3-V preview. On-demand Downloads + optional custom game folder scanning, saved scans, separate Nexus online Updates and all nine games remain intact.
2. Open Install / Update > Compare versions > Review replacement safety (read-only). Find COMPLETE DESTINATION MAPPING & PRESERVATION COVERAGE — READ ONLY.
3. Confirm supported pinned packages/UEVR profiles can show complete recipe install-target counts when a candidate is verified, while missing candidates and real Cyberpunk mappings remain incomplete; no full ZIP or safe update claim is made.
4. Confirm modified configs, unknown binary differences, untracked/manual files, UEVR injector separation and preservation decisions remain blocked for real replacement.
5. Run the existing preview-only TEST FIXTURE ONLY rehearsal: six synthetic rollbacks, six before/after manifests, six complete synthetic target lists and two UEVR retirement holds. Inspect the read-only file rows; game switch resets the result and prior safety review.
6. Verify existing integrity, manual archive, KHARVOX, recovery and installation protections remain unchanged, readable and without overlap.

## Deferred
Full real archive-member accounting and real Cyberpunk destination mapping; exact source/game/runtime compatibility; reconciling current ownership; intentional customization merges; new verified pre-update backups; process locks; live transactional rollback/recovery; user-confirmed protection policies and explicit live-update authority; headset gameplay verification and release publication.
