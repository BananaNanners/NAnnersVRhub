# Dev5D3-J — Pre-Update Safety & Rollback Planning

## Goal
Provide an on-demand, strictly read-only plan of file impact, retained-original backup evidence, archive target mapping, potential collisions, and outstanding prerequisites. Never authorize installation, replacement, repair or restore.

## Facts observed
- Approved parent: Dev5D3-I, a866a36519c7f36cdb4eaf878cd33266f992768b. Clean at worktree creation.
- Hub installers intentionally reject overwriting an existing Hub-managed record. Preserving them is mandatory.
- BepInEx/ERVR and gameroot-2 state retain original-file backup hashes; UEVR-profile-2 stores original whole-directory snapshots. Historical original backups are NOT a fresh backup of today's installed mods.
- Pinned package and UEVR profile ZIP destinations can sometimes be mapped safely using existing parsers. Cyberpunk game-root ZIP wrapper mapping cannot be inferred from raw ZIP entries.
- Existing readiness and installed integrity are advisory; online versions cannot prove compatibility or restore feasibility.

## Proposed defaults
- One Review replacement safety (read-only) button inside the existing collapsed Compare versions panel; no new tab, extra installer or background checks.
- Explicit user action starts a cancellable read-only worker. Check only retained backups under the Hub state directory, with SHA-256 or full directory snapshot comparison. Fail closed for symlinks, missing ownership, inconsistent manifests, stale digests, excessive files or invalid roots.
- Re-hash bounded candidate ZIPs and refuse stale/unsafe changes. Map future destinations only via supported pinned-package and UEVR-profile parsers. Otherwise report Unknown.
- Distinguish previously managed files, proposed targets, ownership conflicts and untracked destination collisions. Display existing integrity status separately from backup evidence.
- Always report that a NEW verified backup of current mod files, compatibility review, dependency-order validation and recovery rehearsal are still needed.
- Report authorized=false and has_live_install_plan=false regardless of other evidence. No new installation or restore permission.
- Clear reviews on game switches, archive rescans, online refresh, and new/cancelled integrity checks. Ensure expanded detail panel scrolls without widget overlap.

## Decision needed
User approved the planning milestone explicitly. No implementation blocker; final real KDE desktop acceptance remains pending.

## Scope
- vrhub/preupdate_safety.py: read-only historical backup/impact and candidate ZIP mapping report with cancellable, bounded hashing.
- vrhub/downloads_gui.py: one explicit safety-review button inside comparison, QThread worker, status/details view, invalidation and safe shutdown, Qt layout minimum-size protection.
- tests/test_preupdate_safety.py: backup, symlink, ownership, stale ZIP, collision and Qt worker fixtures.
- tests/manual_launcher_dev5d3j_preview.py: nine-game isolated KDE GUI harness with synthetic Fatekeeper profile ZIP and historical evidence.

## Safety / rollback
- Isolated branch dev/0.5.5-preupdate-safety-plan; worktree ~/Projects/NAnnersVRhub-0.5.5-dev5d3j.
- All historical Git commits and approved parent retained. Source rollback: Dev5D3-I commit a866a36.
- No writes to real games, mod archives, Proton prefixes, launchers, installed profiles, saved scans, original-file backups, recovery records or the Nexus credential. The worker only reads local evidence when requested. File access time may change depending on filesystem mount policy.
- No actual prospective staging, verified fresh backup, free-space reservation, restore rehearsal, compatibility solver, or live update.
- Existing install/restore safety gates remain unchanged.

## Tests
- Final focused model/UI: 82/82 passed.
- Full regression: 1,115 tests run, 1,114 passed, one skipped. No failures.
- Final isolated nine-game KDE GUI: 367/367 passed, including a synthetic candidate with no replacement authority and no cross-game evidence leakage.
- Visual inspection found compressed disclosure widgets overlapping. Added QLayout.SetMinimumSize and explicit expanded panel minimums; geometry checks show the table, safety detail widgets and later integrity action do not overlap.
- All automated tests use disposable fixture state/ZIPs, not live game files.
- Original shared preview SHA-256 unchanged in tests: state 69bef3d18bbe6fc623ac3ba13969ae011a5949a1f92e49b73c21e0de8504a966; scans 1fbc6109ffb050377dfde0f9b4769204c2d8b32c17ccc4c5838848eba8f71937; folder preferences 05c377e3b3d1beabb9844ee55fbaef822fedbe0ac940e5ac236562e5e3ecefc0.

## Desktop acceptance
1. Expand Compare versions: replacement-safety review starts Not reviewed and never runs automatically.
2. Clicking review for a chosen game gives read-only historical backup status, recorded file impact and future mapping if supportable.
3. Tampered/legacy/unavailable retained originals remain Needs review, and valid historical originals never imply today's mod files have a new backup.
4. Missing archive mapping, collisions and incompatible phases remain review items; never imply automatic compatibility.
5. Scroll the expanded details without overlap; switching games or refreshing evidence invalidates the prior result.
6. Nexus Updates, archive scans, installed integrity, KHARVOX actions, existing backups/recovery and installation gates remain unchanged. No game files or mods are modified.

## Deferred
Transactional new backup creation, actual update replacement or rollback, free-space reservation, verified compatibility solving, Cyberpunk prospective ZIP staging, automatic updating, and headset/gameplay tests.
