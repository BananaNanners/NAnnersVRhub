# Dev5D3-N — Game-Specific Update Staging & Compatibility Validation

## Goal
Develop and validate a game-specific *offline fixture* staging workflow for pinned BepInEx/ERVR packages before connecting any transactional updater to real game directories. Reuse the existing pinned ZIP mapping and safety rules; prove that synthetic future packages can be checked, mapped, interrupted and rolled back without touching existing installations or backups.

## Facts observed
- Approved parent: Dev5D3-M commit `10dc9bd6ad4175178daf0a256c6bc2d68cffd645`, clean at fork.
- Pinned recipe types: Valheim uses two packages with a Thunderstore loader wrapper and VR mod; Subnautica uses two packages with BepInEx and game-data payloads; Elden Ring has one ERVR package whose ZIP entries map beneath `Game/`. Their actual currently approved SHA-256 values and versions stay unchanged.
- The existing `bepinex.archive_plan` validates exact recipe pins, required payload entries, ZIP paths, duplicate/case-insensitive member names, unsafe entry types, and bounded file sizes; it provides the correct mapping from ZIP members to their intended *relative* target names.
- Dev5D3-L's `offline_transaction.fixture_sandbox` can stage arbitrary **invented bytes** in owned temporary fixtures, create and verify new backups, simulate interruption and recover directory topology, but does not accept live game paths.
- Dev5D3-M's integration contract distinguishes draft pinned-package adapters from live execution; all active installers still refuse overwriting a Hub-managed installation.
- No real game-build compatibility data, future recipe pin approvals or actual newer ZIP assets were provided or verified for this milestone.

## Proposed defaults
- Stage only hypothetical test ZIPs, created as in-memory bytes and temporarily materialized under newly created private `/tmp/nanners-dev5d3n-stage-*` directories solely to reuse the existing pinned archive parser. Never accept source/destination archive paths or production game roots as input to this staging API.
- Require a future synthetic package declaration with an **exact SHA-256**, required payload entries, installed and newer plain numeric version labels, a bounded phase, explicit earlier-phase prerequisites and an explicitly declared test game build. Missing, conflicting, malformed or older releases fail closed.
- Do not mistake a declared fixture-compatible build for *verified game/Proton/VR compatibility*. No real-game version, mod compatibility, or upstream release is certified by this milestone.
- Validate mapping and per-file payload hashes; refuse unsafe ZIP members, missing required files, overlapping package destinations, manual/untracked file collisions, differently cased twins, identical/unchanged payload files, missing ownership, unsupported games, and unsafe/nonbyte input.
- Stage only private synthetic destination bytes into a new `offline_transaction` sandbox. Simulate an interruption after a replacement and verify all original owned files, untracked manual settings and directory layout recover. All live-update/compatibility flags must remain false.
- Keep the production interface unchanged. The Dev5D3-N preview alone shows `Rehearse pinned package staging (TEST FIXTURE ONLY)` in the existing preview-only section below `Compare versions`. No live install button or additional production tab.
- Preserve separate online Nexus Updates, downloaded archive scans, installed-file verification, KHARVOX-specific actions, and prior recovery gates unchanged.

## Decision needed
User explicitly requested implementation of Dev5D3-N following desktop approval of M. Offline-only staging and synthetic compatibility defaults are safe and reversible, so no further approval was required to implement them. **Manual KDE desktop acceptance is still pending.** A separate future authorization will be needed before any real mod update.

## Scope implemented
- New `vrhub/pinned_staging.py`: pure, fail-closed fixture-oriented package model; synthetic ZIP bytes with SHA verification and existing package-specific mapper, version/phase/build gates, normalized target manifest and three-game offline interrupted-update/rollback rehearsal.
- New `tests/test_pinned_staging_n.py`: **23 focused staging tests** including three positive game mappings, synthetic rollback, wrong pins, unsupported installers, incompatible build declarations, dependency-order failures, unsafe/duplicate/symlink ZIP members, untracked file protection, source staging scope, stale incoming/installed payload, no-op rejection and no live installer calls.
- New `tests/manual_launcher_dev5d3n_preview.py`: inherits all prior M KDE checks, original saved-scan preservation and synthetic Fatekeeper safety-review tests; changes **preview-only** rehearsal to pinned Valheim/Subnautica/Elden Ring staging with explicit compatibility not verified and live update disabled.
- The approved production `vrhub/downloads_gui.py`, existing source recipes, existing installers, managed-state schema and all earlier checkpoints were not modified in this milestone.

## Safety / rollback
- Isolated worktree `~/Projects/NAnnersVRhub-0.5.5-dev5d3n`, branch `dev/0.5.5-pinned-staging-compat`. Parent M commit `10dc9bd` and every historical worktree preserved.
- No live Steam/Heroic/UEVR file writes, game installation, real ZIP extraction, pinned recipe changes, automatic downloads, real backup mutation, save changes, or Nexus key copy. Staging and transaction writes happen only within self-owned private `/tmp` synthetic fixtures.
- Real installed versions, real game build information, interaction between actual packages, user manual changes across complex games, and actual VR runtime compatibility **remain unverified**. Pin and build data are purposefully invented for testing; no customer-facing `Update verified dependencies` action is enabled.
- On failed staging validation no fixture transaction begins; stale installed/incoming content later fails the offline transaction fingerprint gate. On simulated interruption, restored file bytes and directory topology are verified before reporting success.
- Source rollback: return to approved M commit `10dc9bd`; do not delete or reset preview scans, backups or user preferences.

## Tests
- Targeted integration, transaction-hardening and new staging suites: **60/60 passed**.
- Full regression discovery: **1,198 tests run; 1,197 passed, 1 skipped**; zero failures.
- Final isolated KDE harness: **414/414 checks passed**, across all nine game recipes. Preserved prior UI protections, version comparison and replacement safety reports, user-on-demand archive behavior, and three pinned-package rehearsal outcomes.
- Visually inspected 1630x1060 renders for Valheim rehearsal and synthetic Fatekeeper review. Controls do not overlap, and labels explicitly warn `REAL COMPATIBILITY UNVERIFIED` and `LIVE UPDATE DISABLED`.
- Original shared development preview state, saved scan history and custom folder settings matched their initial SHA-256 values after test runs; final launch should revalidate once again.

## Desktop acceptance
1. The Dev5D3-N KDE preview opens normally; installed archive scanning, comparison and separate Nexus online Updates work as before.
2. Expand `Install / Update → Compare versions`. `Rehearse pinned package staging (TEST FIXTURE ONLY)` starts as **Not run**; it never starts automatically.
3. Clicking the rehearsal reports **Pinned staging PASSED**, covering **Valheim (2 ZIPs, 4 targets)**, **Subnautica (2 ZIPs, 4 targets)** and **Elden Ring (1 ZIP, 2 targets)**, using synthetic releases.
4. Result explicitly says **3 synthetic rollbacks**, **temporary fixtures discarded**, **REAL COMPATIBILITY UNVERIFIED**, and **LIVE UPDATE DISABLED**.
5. Switching games resets the fixture result; the expanded comparison, existing safety review and rehearsal controls remain readable and scroll without overlap.
6. Nexus key, saved scans, custom archive folders, installed-file integrity, KHARVOX controls, backups/recovery, and all existing live installer safeguards remain unchanged. No real game update/repair/restore is triggered.

## Deferred
- Downloading/checking real future pinned releases, changing actual recipe pins, validating real game/build/Proton/VR compatibility and dependency constraints, ownership of live installed files, staging real mod ZIPs, transactional fresh backups of real game roots, real process locks, exact directory-tree recovery under live filesystem races, release approval, live `Update verified dependencies` authorization, and headset gameplay acceptance.
