# NAnnersVRhub 0.5.5-dev5B2 — Verified, User-Authorized Downloads

Status: Implemented and tested offline; awaiting KDE desktop acceptance.
Baseline: approved Dev5B1, commit 01e6a18.
Branch: dev/0.5.5-verified-download-engine
Worktree: ~/Projects/NAnnersVRhub-0.5.5-dev5b2

## New workflow

1. Select a game, open Downloads / Install Plan, and select a package row.
2. Download and verify is enabled only when the CURRENT recipe includes a pinned 64-character SHA-256 and a supported release-page identity. Already verified packages do not need another download.
3. The user pastes an official DIRECT archive asset URL. The hub never guesses links or auto-queries upstream download APIs.
4. The URL must refer to the same GitHub repository/release tag or the same Thunderstore publisher/package/version recorded in the recipe. The URL must be HTTPS without credentials or nonstandard ports.
5. A second, explicit Yes/No confirmation (default No) displays exact game, package, source URL, destination archive filename, and full pinned SHA-256.
6. Only after confirmation does the Qt worker download into a private .part file inside the selected archive folder. Progress and Cancel download controls work while the UI remains responsive.
7. A 3 GiB transfer cap, exact SHA-256 check, known-CDN redirect restrictions, cancellation and error handling prevent unverified output from being retained.
8. A successful matching archive is saved with no-overwrite semantics; if the target name already exists with different bytes, the original is untouched and the download is refused. Identical named or renamed local archives can be reused without any network request.
9. The app reports verified archive saved (NEVER installed) and performs a read-only scan to update this game's local plan. If the user switches games, results stay scoped to the originating game.

## Trust and compatibility limits

- GitHub releases: exact repository and recipe-pinned tag with direct release asset URL, limited redirects to known GitHub release CDNs.
- Thunderstore: exact publisher, package, and pinned version; limited redirects to known Thunderstore CDNs.
- Nexus Mods: manual/browser-only, without bypassing login or guessing protected URLs, even where a pinned digest is present.
- Unpinned UEVR and other manual packages: no in-app direct download until a trusted digest and supported source contract exist.
- Current recipes have eligible pinned direct-source components for Valheim (two) and Subnautica (two). Elden Ring's pinned ERVR file is Nexus-hosted and remains manual-only.
- All currently known pinned archive packages are already present in the user's existing archive library. This means the real Hub will not request duplicate downloads for them.

## Safety properties

- Selecting a game, checking updates, opening a release page or scanning archives never starts a transfer.
- There is no automatic download, auto-install, mod deletion, archive overwrite, save modification or game launch.
- No Nexus credentials or HTTP cookies are used.
- No archive extraction is part of the new worker.
- Cancel and verification failure remove only the newly created private partial file. The original library is preserved.
- The existing game install, Mod Updates, Game Artwork Manager, responsive windows and per-game scan persistence are unchanged.
- Active worker threads block unsafe Hub shutdown; cancellation is requested first.
- The Dev5B2 manual desktop preview has a separate test state and a hard allow_transfers=False safeguard at the UI and worker entry points. It cannot make real network transfers; original Steam/Heroic/game data are not changed.

## Tests

- Simulated HTTP fixtures test URL/source matching, unsafe redirects, authentication failures, wrong hashes, cancellation, large transfers, filename conflicts, and reuse by digest.
- Qt tests check default-No confirmation, invalid URL rejection, no automatic transfers on game switching, progress, cancellation and window-close safeguards.
- The complete inherited Dev1–Dev5B1 tests and real-data GUI preview must pass before desktop handoff.
- No live third-party archive was downloaded during development.

## Dev5B2 KDE desktop checklist

- [ ] Familiar 1630 x 1060 launcher and original branding appear.
- [ ] Downloads / Install Plan shows Download and verify, Cancel download and the progress area.
- [ ] Hover help explains that an exact source and a SHA-256 are required; no automatic install is implied.
- [ ] Cyberpunk Nexus entries remain manual-only and retain Open source.
- [ ] Valheim/Subnautica pinned packages are recognized as eligible, but already verified archives are not duplicated.
- [ ] Preview's live transfer button remains disabled for safety.
- [ ] Existing Cyberpunk/Valheim/Subnautica scan snapshots and timestamps persist when switching games.
- [ ] Folder controls, column resizing, banners, Mod Updates and VR System still behave correctly.
- [ ] No real download, installation, or existing game/archive/save changes occur.
- [ ] User approves Dev5B2's UI and explicit-download policy.

Next: Dev5C will handle guided installation consent, conflict and backup previews, and phase-order controls. Dev6 remains dedicated per-mod rollback.
