# Dev5D3-M — Real-Installation Update Integration Readiness

## Goal
Prepare non-executable, read-only integration contracts for eventual transactional updates across the Hub's different mod installation workflows. Preserve existing live-execution restrictions, backup records, mod ZIPs, and all game files. Keep the UI clean by reusing Review replacement safety (read-only).

## Facts observed
- Approved parent: Dev5D3-L commit 7b50369524eccef2816fd11b15f7bc97a1486664, clean at fork.
- Nine current recipes describe 27 dependencies: Cyberpunk 2077 has 15 Nexus game-root components; Valheim and Subnautica have two pinned BepInEx packages each; Elden Ring has one pinned ERVR package; Fatekeeper and Hogwarts Legacy each have a separate manual injector and UEVR profile; DOOM, Skyrim VR MGO, and Ready or Not retain guided/manual pathways.
- Existing live installers refuse to overwrite managed installations; UEVR profile live execution has an additional disabling gate. These restrictions must remain unchanged.
- Installed provenance, SHA-256 integrity, archive identity, and prospective destination mapping are independent evidence sources. Historical backups are not fresh pre-update backups.
- Dev5D3-L's transactional engine runs only on private synthetic /tmp fixtures. Successful synthetic recovery does not validate any real game compatibility or rollback.

## Proposed defaults
- Create versioned per-dependency read-only contracts with adapter type, target scope, expected installer marker, dependency phase, recorded ownership, on-demand integrity, uniquely identified future release, prospective destination map and explicit outstanding blockers.
- Adapter groups: pinned_package for BepInEx/ERVR, uevr_profile for recorded UEVR profile trees, gameroot for Nexus component installs; uevr_injector and manual remain unsupported for automated replacement.
- Validate nonescaping canonical recorded file paths, matching installer markers, pinned SHA consistency, game-root ownership, UEVR snapshot size/directory evidence, unique component integrity and matching game identifiers. Missing or malformed evidence must remain unverified.
- Every contract retains six mandatory future requirements: no live executor connected, fresh complete verified backup, game-stopped lock, compatibility/dependency review, real rollback validation, and explicit separate authorization. Even fully matched historical evidence never authorizes execution.
- Reuse the existing Review replacement safety button; append a concise UPDATE ADAPTER CONTRACTS section after a user-initiated review. No extra production update button or automatic check.
- Preview only: Rehearse update adapters (TEST FIXTURE ONLY) runs three independent synthetic interrupted-update/recovery tests. It never calls a live installer, download action, or real game path, and clears the test result on a game switch.

## Decision needed
User explicitly started Dev5D3-M after desktop-approving L. No blocker for the conservative read-only milestone. KDE desktop acceptance remains pending. No live update authorization is granted.

## Scope implemented
- vrhub/update_integration.py: pure contract model and three fully synthetic offline transaction rehearsals. The contract analyzer does no file or network I/O.
- vrhub/downloads_gui.py: the on-demand PreUpdateSafetyWorker attaches integration contracts after its safety review, and the existing detailed report displays missing prerequisites and adapter types. Existing installation and recovery functions are untouched.
- tests/test_update_integration_m.py: all nine recipes, installer ownership markers, pinned hashes, game-root and UEVR profile evidence, manual/injector distinctions, stale/colliding paths, cross-game isolation, duplicate decisions, and proof existing live installers are never invoked.
- tests/manual_launcher_dev5d3m_preview.py: nine-game disposable KDE harness with synthetic Fatekeeper adapter report and three-adapter fixture rehearsal, inheriting the approved earlier desktop checks.

## Safety / rollback
- Worktree ~/Projects/NAnnersVRhub-0.5.5-dev5d3m on branch dev/0.5.5-update-integration-contract, forked from approved L commit 7b50369.
- No real game files, mod ZIPs, Steam/Heroic prefixes, VR profiles, user state, saved scans, backup history or Nexus credentials modified. The existing credential remains read-only in the preview.
- Every result says authorized=false, replacement_supported=false and live_executor_connected=false. No permission tokens or executable update contracts are produced.
- Offline adapter rehearsals use invented bytes inside temporary fixture sandboxes only and discard them. Source rollback returns to approved L, with no reset/deletion of user-owned state.

## Tests
- Focused integration, recovery and safety suites: 78/78 passed.
- Full regression: 1,175 tests run; 1,174 passed, one skipped; zero failures.
- Nine-game disposable KDE GUI: 405/405 checks passed. Fatekeeper synthetic safety report, Valheim adapter rehearsal and Cyberpunk retained protection warning visually inspected.
- Original shared preview state, saved scan history and folder preferences remained byte-for-byte identical.

## Desktop acceptance
1. Dev5D3-M preview opens; archive-first scanning and separate Nexus Updates continue as before.
2. Expand Install / Update → Compare versions, then click Review replacement safety (read-only); the report includes UPDATE ADAPTER CONTRACTS with type, evidence gaps, and explicit live-execution blocks.
3. Fatekeeper/Hogwarts show separate manual injector and draft UEVR profile; Cyberpunk preserves per-component game-root limitations; guides remain manual.
4. Preview-only Rehearse update adapters (TEST FIXTURE ONLY) reports three synthetic rollbacks, temporary fixtures discarded, and LIVE UPDATE DISABLED.
5. Switching games clears the preview rehearsal result and invalidates the previous safety review. Controls scroll without overlap.
6. Nexus, installed-file integrity, KHARVOX specialist tools, manual selection, backups/recovery and all installation gates remain intact. No real game writes, replacements, or restores occur.

## Deferred
Enabling any live mod replacement; complete fresh real-install backups, lock/stop checks, exact ZIP staging, UEVR injector ownership, profile whole-directory live recovery, recipe-pin changes, full compatibility validation, real power-failure testing, VR headset acceptance and publication.
