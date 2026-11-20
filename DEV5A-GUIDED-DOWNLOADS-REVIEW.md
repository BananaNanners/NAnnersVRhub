# NAnnersVRhub 0.5.5-dev5A — Guided Downloads & Install Plan

**Status: Dev5A foundation implemented; user KDE acceptance pending.**

**Approved baseline:** Dev4 commit `d263c9c`, branch `dev/0.5.5-artwork-manager`.

**Development branch:** `dev/0.5.5-guided-downloads`, worktree `~/Projects/NAnnersVRhub-0.5.5-dev5`.

## Scope of Dev5A

This is the **first step of Dev5**, not a claim that new automatic downloads or one-click installation have been implemented. These require separate permissions, upstream-source verification, safe download verification, test evidence, and explicit user approval. There are no new network requests, automatic downloads, mod installations, game launches, deletions or installs triggered by this new page.

1. A fifth tab, **Downloads / Install Plan**, is available for all nine game profiles; the previous four tabs retain their exact indices.
2. Automatic local discovery of `~/Downloads/Organized/Archive-Library/VR-Mods/` when present, else `~/Downloads/`. Scans are read-only, bounded to two subfolder levels with symlink directories ignored and at most 1,800 archive candidates.
3. **Set default folder…** selects a new global archive library. **Set this game's folder…** can override it for one profile. **Use default folder** clears that override. **Reset default** returns to automatic discovery. These choices write only to `download-folders.json` beside the Hub's own state file, with a locked atomic update; the preference file cannot silently replace invalid existing data.
4. Previously supported **Install mod file…** and **Install profile…** file pickers open at the configured local folder, but their original verification/install behavior is unchanged. No scan triggers these installers.
5. **Scan local archives** runs in a Qt background worker with a busy indicator so the GUI stays responsive. It inventories filenames and sizes without extracting or modifying archives. Pinned recipe hashes are checked using SHA-256 with an explicit 3 GiB scan budget and a small in-memory metadata cache. A valid hash equals a trusted pinned recipe digest; a filename match alone never does.
6. Native per-component table: **Component/package**, **Install stage**, **Local archive**, **Verification**, and **Open source** button. Each Open source button requires user action, validates HTTPS, and opens the maintainer's recipe-defined download/release page through the browser; it does not fetch files.
7. Cyberpunk 2077's **15 dependency rows** preserve their recipe order. The final CyberpunkVR Port is labelled **Later: install after first flat launch**; no UI shortcut can install it automatically in stage 1.
8. Three safety outcomes are separate: **Pinned SHA-256 verified** (green), **Possible archive — inspect first** (yellow), **Hash mismatch — do not install** or **Hash not verified — do not install** (red). Missing archives are reported explicitly.
9. **Inspect selected archive (read-only)** delegates to the existing validated game-root/BepInEx/ERVR staging inspector, which cleans its temporary staging folder. UEVR profiles and guide-only recipes use their established Setup guide rather than claiming unsupported generic inspection.
10. Existing game dashboards, Steam/Heroic artwork, Nexus/GitHub update checks, controller tabs, VR System, responsive layouts and the 1630×1060 opening size remain unchanged. Original banana yellow, charcoal and cyan remain the theme.

## Real archived files inspected (read-only)

**28 local archives** found in the existing VR-Mods library, without changing any archive.

| Game | Local plan result |
|---|---|
| Cyberpunk 2077 | 15 filename/Nexus-ID matches; all explicitly **possible / inspect first**, none falsely hash verified. VR Port stage 2. |
| Valheim | 2 packages match the existing recipe-pinned SHA-256 digests. |
| Subnautica | 2 packages match recipe-pinned SHA-256 digests. |
| Elden Ring | 1 ERVR package matches the pinned digest. |
| Fatekeeper | 2 filename candidates need manual/recipe inspection. |
| Hogwarts Legacy | 2 filename candidates need manual/recipe inspection. |
| Ready or Not | 1 filename candidate needs manual/recipe inspection. |

The found library also contains older revisions; filename matching **does not** imply an archive is current or appropriate for the user's installed game patch. Version comparisons remain in the Mod Updates tab. Pinned package digests check archive identity, not gameplay compatibility.

## Safety boundary

- Released NAnnersVRhub 0.5.4 and approved Dev1–Dev4 checkpoints untouched; Dev5A uses its own Git worktree.
- The manual preview uses a private copy of the saved state at `~/.cache/nannersvrhub-055-dev5-state-20261120/state.json` and separate XDG configuration/cache/data. Choosing or resetting a folder in the preview writes only to this private copy's preferences. The real game files, saves, Steam/Heroic data and production Hub preferences remain unchanged.
- Preview disables normal installer actions, uninstall, game launches, Hub self-updates, recovery actions and other mutating operations.
- Archive scanning and pinned digests are read-only. Temporary inspected archives are managed by the existing `hub.inspect_archive` staging cleanup.
- Folder selection is user-initiated; no background network requests are created by the new page. All external-source pages are HTTPS and require a click.
- A scan result is a **planning aid**, not authorization to overwrite a mod. Existing install safety gates remain in place.

## Dev5A KDE desktop acceptance checklist

- [ ] Window opens comfortably at **1630×1060**, with all original navigation and branding.
- [ ] **Downloads / Install Plan** appears as a fifth tab for any selected game.
- [ ] The existing VR-Mods archive-library path is discovered automatically.
- [ ] **Scan local archives** shows 15 Cyberpunk candidates without calling them verified.
- [ ] CyberpunkVR Port is clearly marked as a later-stage installation.
- [ ] Switch to **Valheim**: both packages show pinned SHA-256 verified (green).
- [ ] Switch to **Subnautica**: both packages show pinned SHA-256 verified (green).
- [ ] Switch to **Elden Ring**: the ERVR archive shows pinned SHA-256 verified.
- [ ] **Set default folder** and **Set this game's folder** work, with **Use default** and **Reset default** restoring the desired location. Test changes stay isolated.
- [ ] **Open source** opens an appropriate official mod/release page; **Inspect selected archive** remains read-only.
- [ ] The existing Setup guide, Mod Updates, Game Artwork Manager and VR System remain usable.
- [ ] Resizing works at compact sizes without overlapping controls.
- [ ] No games, mods, Steam/Heroic settings, saves, installed release, or production Hub preferences have changed.
- [ ] User confirms Dev5A approval before any automatic downloader work begins.

## Planned continuation after Dev5A

**Dev5B — Explicit user-authorized downloads** with source allowlists, manifest-pinned archives, progress, resume/failure handling, controlled final destination and verification before a file may be offered for installation. Do not download Nexus-protected files without permitted authentication; if direct fetch is unsupported, use the browser/manual download workflow.

**Dev5C — Guided installation confirmation & rollback preflight** with package/source verification, ordered phases, reviewed conflict/backup policies and explicit opt-in; preserve the existing transactional installers and game saves. No automatic install triggered by a version check or source click.

**Dev6 — Per-mod rollback manager** after Dev5's verified installer operations.

## Final automated verification and desktop handoff — November 20, 2026

- **726 regression tests run: 725 passed, 1 skipped** (Qt offscreen).
- **55/55 read-only Qt preview checks passed** against the real archive library and a private copy of the user's Hub state.
- Verified exact real-library hashes for 2 Valheim packages, 2 Subnautica packages, and 1 Elden Ring package; Cyberpunk filename candidates remain expressly unverified.
- Existing Dev1–Dev4 launcher, dashboard, artwork, update-check, resilience and window sizing tests all passed.
- At 1630×1060 the five location/scan buttons adapt to a single toolbar row; on compact layouts they wrap to two columns. The original games-page scroll remains free of horizontal overflow.
- Closing the Hub during an active local archive scan is blocked until the Qt worker exits normally; the idle signal then resumes safe close. Regression check passed.
- Real-data preview never enabled installation, game launches, uninstall, backup recovery or automatic download actions. Folder preference edits in this preview stay inside its private XDG test state.
- Final Qt captures are local QA files under `~/.cache/nannersvrhub-055-dev5-preview.png` and `~/.cache/nannersvrhub-055-dev5-plan-tab.png`, not bundled third-party content.
- **User acceptance of Dev5A is still pending.**
