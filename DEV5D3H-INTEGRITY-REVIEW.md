# Dev5D3-H — Installed File Integrity Verification

## Goal
One on-demand **Verify installed files** action per selected game, using only trustworthy Hub-managed SHA-256 manifests. Report unchanged, modified, missing, unsafe, or unknown evidence. Surface file details only when a result needs attention.

## Facts observed
- Approved parent: Dev5D3-G commit 6b1dadf9ac6582f184ebfe79ac0834a63af8415b. Parent worktree clean before starting.
- Pinned BepInEx/ERVR installers record installed file hashes in file_hashes and per-package files plus pinned release IDs; Cyberpunk game-root v2 installer stores per-component file lists and global installed_sha256, keyed by relative game-root filenames.
- Newer UEVR profile installer saves root path, complete installed file manifest with relative per-file SHA-256 and sizes; older profiles lack these records and must remain Unknown.
- Existing archive scans and download folders are distinct from installed-file manifests. The user approved one click per game, no background checks, details only when needed, no game modification or automatic repair.
- The shared development-preview Nexus key is read via a strictly read-only fallback from Dev5D3-F1. Do not copy it or weaken live installation gates.

## Proposed defaults
- One visible **Verify installed files** button below Compare versions on Install / Update; pressing it starts a bounded local SHA-256 job in a worker QThread; button offers cancellation while running.
- Not checked by default. For supported Hub records: require owning installer marker, valid canonical stored installation root and equality with the detected game path; reject missing/inconsistent records before reading files. Inspect only per-package or per-component tracked paths.
- Do not follow symlink file targets, symlink root, or symlink ancestors within the opened game root. Use openat-style dirfd traversal, O_NOFOLLOW, regular-file checks, SHA-256 digests and size/mtime/inode rechecks. Refuse parent-path escapes and unsafe record strings.
- Enforce 2500 maximum recorded files, 512 MiB per file, and 2 GiB per run. Fail closed as Unknown for unsupported or unsafe operations. Cancellation never yields a successful result. Qt worker stops when closing the app.
- Concise one-line result counts for all checks. A read-only details field is hidden when all checked files match, and reveals only missing, modified, unsafe, unknown or incomplete records.
- No action on a game switch can carry a result into another game. A new scan or game selection starts with Not checked. This does not alter the existing archive scan, online update, installation, or rollback gates.

## Decision needed
No additional blocker for the offline implementation: user explicitly approved on-demand full selected-game checks. **KDE desktop acceptance is required** before calling this milestone approved.

## Scope
- Add vrhub/installed_integrity.py: pure on-demand SHA-256 verifier (read-only filesystem operations). No state writes, data adoption, downloads, or network requests.
- Add InstalledIntegrityWorker and button, status, optional details widget in vrhub/downloads_gui.py. Existing comparison table and folder UI remain intact.
- New tests/test_installed_integrity.py covers read-only success, modified/missing, symlink refusal, unsafe/overlapping manifests, root identity, state pin conflicts, read limits, cancellation, Cyberpunk manifests, profile snapshots and one real Qt click-driven worker against disposable files.
- New tests/manual_launcher_dev5d3h_preview.py: nine-game GUI harness and fixture evidence; it inherits read-only Nexus credential handling, and does not open real game files during automated verification.

## Safety / rollback
- Isolated Git branch dev/0.5.5-installed-integrity and worktree ~/Projects/NAnnersVRhub-0.5.5-dev5d3h. Preserve every previous checkpoint and current game installations.
- No real game-file writes, removal, restoration, auto-repair, profile replacement, release update or changing game runners. No file storage schema changes, scan resets, or rewriting history.
- SHA matching is bounded evidence about recorded files **at that instant**; it is not verification of mod loading, game compatibility, manual/untracked mods or VR function. Files outside the Hub manifest remain unchecked even if they exist.
- The verifier's read-only access can update filesystem atime according to system mount settings. It does not intentionally write data.
- Restore source by returning to the approved 6b1dadf checkpoint. User-owned preview scans/preferences/state are not migrated or overwritten.

## Tests
- Focused integrity and comparison tests: 42/42 initially passed after fixing a directory-fd wrapper issue. Expanded focused tests: 66/66 passed; Qt click/worker lifecycle suite: 18/18 passed; GUI lifecycle-focused set: 41/41 passed.
- Final full unittest discovery: **1,066 run, 1,065 passed, 1 skipped**.
- Final nine-game disposable KDE GUI verification: **230/230 passed**, including a disposable synthetic Valheim file tree (one tracked file Verified; other package Unknown).
- Screenshots inspected visually for Valheim fixture, Fatekeeper and Cyberpunk at KDE 1630×1060.
- No real-game hashing occurred in automated tests; user approval is needed to test on a live installed game, with the action itself read-only.

## Desktop acceptance
1. Inspect the one **Verify installed files** button for every selected game under Install / Update; status starts **Not checked**.
2. For a game with valid historical post-install file hashes, click once; the Hub displays matched count and verified/review/unknown breakdown. Check only a game you choose.
3. Unknown/manual/legacy records remain **Unknown**, not erroneously green.
4. Detailed results appear only for unknown, missing, modified or unsafe entries; success remains compact. Do not intentionally modify a working game merely to trigger a warning.
5. Switching games and reopening the preview does not reuse a prior integrity result or disturb saved scans/custom folder settings.
6. Updates/Nexus key and existing archive SHA verification, installation review, backups and recovery gates remain unchanged. No repair or installation is initiated.

## Deferred
Scheduled/background checks; automatic repairs; installed release provenance schema changes; checking arbitrary manually added files, broad folder crawling, automatic updates, real VR gameplay checks or executing any blocked installation gate.
