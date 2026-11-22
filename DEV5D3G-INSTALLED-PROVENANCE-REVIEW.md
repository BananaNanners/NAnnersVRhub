# Dev5D3-G — Installed Dependency Evidence & Version Provenance

## Goal
Improve the read-only Installed (Hub) comparison column by attributing release labels only to evidence from prior Hub installations, distinguishing pinned package hash, official profile source hash match, recorded filename hint and unknown/manual possible. Do not modify installed game files or authorize an update.

## Facts observed
- Parent is desktop-confirmed Dev5D3-F1 commit 63f70f739537f7b586fc697b0ae9539b12d35167. Its worktree was clean.
- Subnautica, Valheim and Elden Ring package installers already record per-package SHA-256, archive names and installed file inventories, while recipes include pinned archive hashes and release source pages. Existing verification checks file presence, not current bytes.
- Newer UEVR profile records can store original source ZIP hash and an installed file manifest. Profile live execution remains disabled under the existing safety gate. Older UEVR profile state may not identify a release.
- Cyberpunk has per-Nexus-component recorded archive names and file manifests but not a cryptographically established Nexus release identity.
- Downloaded archive SHA evidence and the separate online GitHub/Nexus update check never establish the installed version by themselves.

## Proposed defaults
- Use a pure read-only installed_provenance.evidence model; no new filesystem or network reads.
- Display Recorded pin plus explicit release tag only when an owning installer marker, per-package SHA-256 and installed-file record match the current pinned recipe. A changed recipe pin yields Recorded hash · pin differs rather than mislabeling historical evidence.
- For UEVR profiles, Recorded profile plus tag requires a new-format profile record with original source SHA, valid installed snapshot and an exact unique digest-to-tag match to the configured official GitHub profile release inside a complete active scan.
- Cyberpunk displays Recorded filename plus version only for valid per-component Hub archive records; never calls this cryptographically verified.
- Show Unknown or a historical-record-only label for manual, partial, stale, ambiguous or old records.
- Leave the main archive checklist and installer safety controls unchanged. Use source descriptions in the existing comparison tooltips, not another button.

## Decision needed
No blocker for offline prototype. User explicitly requested the milestone. Actual KDE desktop acceptance is still pending.

## Scope
- New vrhub/installed_provenance.py with pure immutable provenance classification.
- Integrate into vrhub/archive_update_comparison.py and update the summary/note in vrhub/downloads_gui.py.
- New tests/test_installed_provenance.py and updated existing comparison expectations for more precise labels.
- New tests/manual_launcher_dev5d3g_preview.py, a disposable nine-game GUI verification harness and safe read-only desktop preview retaining Dev5D3-F1 Nexus key behavior.

## Safety / rollback
- Isolated branch/worktree; preserve parent and every earlier Git checkpoint.
- No production game file writes, archive extraction, real installation, download, game-root hash checks, saved state mutations or new state schema.
- Recorded archive hashes prove only what Hub tracked when the package was selected; do not imply current installed bytes, runtime compatibility or safe upgrades.
- Return to parent 63f70f7 to roll back source. Never overwrite the user-owned preview state, scans or folder settings.

## Tests
- Focused suites: 80/80 passed including previously approved install/backup controls.
- Focused additional profile source tests: 26/26 passed.
- Full regression: 1,048 run; 1,047 passed, 1 skipped.
- Isolated nine-game KDE GUI: 199/199 passed. Valheim/Subnautica recorded pin screenshots are TEST FIXTURES with synthetic in-memory state, not claims about current real installed mod files.
- Visually inspected Valheim, Subnautica, Cyberpunk and Hogwarts Legacy views (1630 x 1060); unchanged review action safety and disabled live game actions.

## Desktop acceptance
1. Pinned package version labels appear only where Hub recorded the matching archive hash.
2. Cyberpunk distinguishes Recorded filename from cryptographically attributed release.
3. UEVR profile history with no match remains unknown; matched official hashes carry a recorded-source-only label.
4. The five-column archive checklist is unchanged; unknown or stale evidence cannot enable an installation.
5. Nexus-powered Updates remains independent; saved scans and per-game folder choices persist across restart.
6. No game-file writes, automatic updates, profile installations or recovery changes.

## Deferred
On-demand verification of current installed game-file bytes, new future install-time release provenance schema, manual-mod adoption, automatic downloads and updates, runtime/VR gameplay verification, or any live gate changes.
