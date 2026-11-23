# Dev5D3-X — Archive Payload Classification & Compatibility Evidence

## Goal
Classify Cyberpunk 2077 ZIP member filenames and metadata as installable-looking, recognized documentation, possible optional, unknown, or unsafe. Explain incomplete ZIP mapping without relaxing the approved W strict-mapping or live-update refusal gates.

## Facts observed
- Approved parent W: commit 5d5faf0f871536450f9e94d77ccecd1654f0022b, clean at fork. No authorization for live updates, repairs, backup writes, or ownership adoption.
- W requires every regular ZIP member to become a supported game-root install target. The legacy game-root installer can silently ignore files outside recognized game roots. X explains those members but does not permit skipping any of them.
- The existing strict preflight rejects path traversal, symlinks, duplicate casefold names, encrypted files, unsupported member types, and oversize ZIPs. X preserves this gate.
- Most of the 15 Cyberpunk components lack a separate required-file contract. Nexus IDs parsed from filenames are not source authentication or compatible game-build proof.
- Metadata-only inspection of selected files named in an older saved Cyberpunk scan: 14 available ZIPs, 1 non-ZIP selected file. Classification counts: 1,461 installable-looking mapped paths; 1 documentation-looking entry; 4 unknown entries; no optional entries or unsafe metadata signals. Component #18002 had 3 mapped plus 1 unknown member. Selected VR Port #30093 had 1,329 mapped, 1 documentation-looking, 3 unknown, and did not satisfy the recipe-required payload check. Saved scans included several alternate matches, which were not inspected as automatic update candidates. These are descriptive findings, not proof of release authenticity, newest version, correct runtime compatibility, or actual installed-mod integrity.

## Proposed defaults
- Use a deliberately narrow filename/metadata-only taxonomy. Recognized root- or single-wrapper-level README, LICENSE/LICENCE, COPYING, CHANGELOG, CHANGES, CREDITS and AUTHORS text/Markdown names may be described as documentation-looking. Other names and unrecognized nested paths stay unknown.
- Root- or wrapper-level Optional, Optionals, Optional Files, Alternatives, or Variants folders mean possible optional content, not automatic selection/exclusion. Files under mapped game installation roots remain installable-looking even if their filenames resemble documentation or optional files.
- Documentation or optional labels do not waive W's full regular-member install-target requirement. Any unmapped member still blocks a complete installation mapping. Unsafe or malformed ZIPs produce only a sanitized unsafe signal, never invented exact member counts.
- Classify only through the existing explicitly triggered read-only replacement safety review, after the selected candidate's digest and size checks. Recheck the digest after classification and after W mapping; clear evidence on mutation, read failure, or stale mapping.
- Keep the complete evidence boundary explicit: source authenticity, newest release, game-build/runtime compatibility, dependency correctness, ZIP member CRC/content integrity, current installed ownership, fresh pre-update backup, and live update authorization all remain unverified/false. Required recipe file presence, where defined, is not full compatibility proof.
- Keep all original archive-first controls, Downloads plus optional custom folder scanning, separate Nexus Updates, integrity review and recovery safety gates. Add no new production action. Show one compact read-only section in the existing safety details and five disposable classification fixtures in the existing TEST FIXTURE ONLY rehearsal.

## Decision needed
The user explicitly started Dev5D3-X after approving W. Conservative read-only classification was implemented; manual KDE desktop acceptance is pending. Approval of this milestone does not authorize archive exclusions, optional variant selection, installing updates, rewriting hashes or backup/recovery operations.

## Scope
- vrhub/payload_evidence.py: bounded read-only ZIP metadata taxonomy; sanitized member examples; restricted documentation and optional classification; required-file evidence; all version/source/compatibility and authorization flags false. Five disposable invented ZIP fixtures.
- vrhub/preupdate_safety.py: attaches transient payload evidence to the existing Cyberpunk on-demand review even when W strictly refuses an archive with unmapped members. Clears payload evidence when the ZIP digest changes. No persistent records or installer action.
- vrhub/downloads_gui.py: adds ARCHIVE PAYLOAD CLASSIFICATION & COMPATIBILITY EVIDENCE — READ ONLY to the existing scrollable report, showing safe counts and examples, and explicit source/compatibility warnings.
- tests/test_payload_evidence_x.py: direct/wrapped documentation, alternatives and unknowns, inside-install-root mapping, present/missing required VR Port files, unsafe paths/symlinks/duplicates, ambiguous IDs, digest changes during classification/final mapping, no ZIP member payload reads or writes, Qt report lifecycle.
- tests/manual_launcher_dev5d3x_preview.py: preserves all W KDE checks; adds synthetic Cyberpunk mixed-content ZIP and report-rendering checks, strict mapping refusal and game-switch invalidation, plus five classification fixtures in the existing preview-only rehearsal.

## Safety and rollback
- Isolated worktree ~/Projects/NAnnersVRhub-0.5.5-dev5d3x on branch dev/0.5.5-payload-classification-evidence, forked from desktop-approved W. Approved W and earlier checkpoints untouched.
- ZIP member payloads are never opened/extracted by the new classifier. The existing on-demand review still computes a whole-archive hash to tie metadata to the selected candidate. No real game, ZIP, mod, Steam/Heroic prefix, UEVR profile, save, backup, ownership hash, archived scan, custom archive folder or Nexus credential changed.
- Test ZIPs contain invented data in disposable temp directories. Real archive spot-check files were read only at ZIP metadata level; paths, credentials and source content are excluded from the Git report.
- Return to approved W worktree to roll back code. Never reset saved scans or remove user-owned recovery copies.

## Tests
- Focused X/W/pre-update safety suite: 87/87 passed. Initial tests expecting blocked unsafe/ambiguous classification to vanish were corrected to require informative blocked evidence and no authority.
- Full regression: 1,476 tests run, 1,475 passed, one skipped; no failures.
- Final isolated nine-game KDE harness: 558/558 passed. The Cyberpunk payload classification report and original controls were visually inspected at 1630x1060.
- Shared development-preview state, saved scan history and custom archive folder preferences retained their starting SHA-256 values. Nexus credential never copied or modified.

## Desktop acceptance
1. Open X preview. Verify existing on-demand Downloads/custom folder scans, saved inventory, nine-game navigation and separate Nexus updates.
2. Cyberpunk > Compare versions > Review replacement safety (read-only) shows ARCHIVE PAYLOAD CLASSIFICATION & COMPATIBILITY EVIDENCE, with counts of installable-looking, documentation-looking, optional, unknown and unsafe members when a candidate is unambiguous.
3. Confirm documentation names are not automatically excluded, optional alternatives are not auto-selected, and unknown/unsafe members still block strict complete target mapping; the selected VR Port #30093 remains review-required.
4. Confirm Nexus release identity, newest version, game-build/runtime compatibility, CRC, current ownership, fresh backup and recovery remain unverified, and no live update or restore is offered.
5. Run the existing TEST FIXTURE ONLY rehearsal: six synthetic rollback cases, six manifests, two accepted/four rejected W ZIP layouts, five new X classification fixtures, and two UEVR retirement holds; game switching clears old results.
6. Confirm installed-integrity review, KHARVOX tools, backup/recovery, archive controls, previous safety gates and GUI readability remain intact without new production buttons or overlaps.

## Deferred
Trusted per-component documentation-exclusion policy, user-controlled optional variant choices, streaming archive member CRC/data verification, authenticated Nexus release identity, actual game/VR compatibility, current ownership reconciliation, protected configuration merging, fresh backups and runtime process locking, real transactional recovery and separately approved live updates.
