# Dev5D3-E2 — Downloads plus custom archive scanning

## Goal
On-demand scan of ~/Downloads and one optional per-game/shared archive folder, with independent online update checks. Prevent repeated folder selection, identify duplicates and different releases, and retain previous scan evidence across development stages.

## Facts observed
- Parent checkpoint: da60471c93848a33e67f499346f61b345d6a57fa (Dev5D3-E1, desktop acceptance had failures). New isolated worktree and branch.
- Prior planner and saved-scan validator assumed one root. The shared default was a fallback, not an additional scan location, creating confusing labels and inactive results after changing folders.
- User's existing shared development preview contains historical per-game scan records and explicit overrides. It was not migrated, reset, rescanned, or overwritten by development tests.
- Nexus/GitHub online update checks stay independent of the on-demand archive inventory; GitHub release SHA metadata used for local archive identity remains unchanged.

## Proposed defaults / decision
Approved in conversation: always include Downloads; add at most one optional folder (explicit game folder first, otherwise shared extra). Same physical paths are inventoried once. Choose folders manually and scan on demand. No background monitoring. No additional user decision required for this isolated implementation.

## Scope implemented
- planner.scan_folders returns Downloads plus optional extra; _inventory_many combines two bounded, non-symlink roots and deduplicates repeated paths when folders overlap. Existing candidate digest matching, copied ZIP grouping, official release prioritization and hash limits remain.
- Folder menu now uses "Add game archive folder", "Choose shared extra folder", "Use shared extra for this game", and "Remove shared extra folder". Only actual scanned locations appear beneath Archive Dependencies.
- The normal scan worker scans both roots. Result persistence and review revalidation bind the exact folder combination, preventing a one-folder historical scan from authorizing review of two folders. If any root is inaccessible or limits are exceeded, warnings block automated review.
- Saved scan store is backward-readable for schema1. A user-requested new scan writes bounded schema2 history keyed by game and root combination. Previous combinations are retained (max eight; fail without deleting when full). Before first schema1 upgrade, save and verify archive-scan-snapshots.pre-multifolder-v1.json. No automatic migration at startup.
- Existing preview storage discovery reads schema2 safely, without reinstating old scans. Older Git worktrees may not read schema2 directly; the protected schema1 copy is the manual rollback source, never restored automatically.
- All original installer, transfer, verification, UEVR profile, game-root backup, KHARVOX and launch gates preserved. No live installation or game-file access beyond read-only scans.

## Safety / rollback
- No edits to original game files, mods, archives, installed apps, historic Git commits, or development-preview scans/preferences/state.
- New Git branch/worktree provides source rollback to da60471c. A saved-scan schema1 backup is made automatically only on the user's first new combined scan, and verified before mutation; do not auto-restore.
- Unknown or stale archive evidence remains non-installable. Missing root and partial inventory require rescan. No automatic version choice by filename alone.

## Tests
- Focused tests for history migration, dual-root discovery, nested-root deduplication, pinned/candidate identity, official version priority, symlink refusal, invalidated files, history capacity, cross-process schema2 read: passed.
- Final full suite: 1,012 tests, 1,011 passed, 1 skipped. No failures.
- Nine-game disposable saved-data KDE GUI run: 119/119 passed. Uses copy of existing private preview data. Final rendered Fatekeeper and Valheim interfaces inspected at 1630x1060.
- Shared state, saved scan and folder preference SHA-256 unchanged after verification: state ed2884a7ada0ec0364c32d86215fbae0f972fbb0530ea14a416c8e054089d16c; scans 4168d241b18d1385ad1285a26d318d040fe0197eeb152270846d59927ae49e4b; preferences bec5f367f10f4ab103be245f34308428e374790f8a9f2ad88378f4f3ac42f8a6.

## Desktop acceptance
Pending user testing: Downloads always listed; custom folder appears as second scan location; scan selects archives from both; duplicates grouped and different versions remain review choices; switching game retains preferences; changing optional folder does not delete old scans; pinned Subnautica and Valheim sets continue to open safety review where verified; no live install enabled. One new combined scan per game is needed before former single-folder snapshots can be used for combined verification.

## Deferred
Background filesystem watch, automatic installer, automatic archive moves, version/compatibility acceptance, game updates, headset gameplay, publishing, and any removal of saved history.
