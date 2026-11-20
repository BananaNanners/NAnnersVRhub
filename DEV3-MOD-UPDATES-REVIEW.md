# NAnnersVRhub 0.5.5-dev3 — Dedicated Mod Updates

**Status: Implementation complete for desktop review. User acceptance pending.**

**Development branch:** `dev/0.5.5-mod-updates` in isolated worktree `~/Projects/NAnnersVRhub-0.5.5-dev3/`.

**Baseline:** approved Dev2 branch `dev/0.5.5-game-dashboards`, commit `a661cdc`.

## Implementation

- Adds a **Mod updates (N)** tab in each game's details panel. The original three tabs keep their existing positions and logic: Setup guide (0), Compatibility profile (1), Controller bindings (2); new Mod updates (3).
- Replaces the lengthy repeated update entries in the active Qt Setup guide with a **compact summary and instruction to use the Mod updates tab**. The original `hub.details_html()` defaults remain unchanged for legacy and non-GUI callers.
- Each mod row displays **name**, verified known **installed version**, server-reported **latest version**, explicit **status**, and **Open source** link. Unknown versions use a dash; the UI does not guess.
- The existing single update-check worker is reused, including the Cyberpunk component-version tracking fixed in earlier milestones. No duplicate API calls are launched by opening a tab.
- Native status groups: **Updates available**, **Needs review**, **Install later**, **Not installed**, **Up to date**. The `Up to date` group starts **collapsed** by default, can expand and collapse, and remembers expansion while viewing the same game.
- The **Mod updates** tab is available across all nine existing game profiles, including legacy GitHub/manual release recipes (which may not identify a local version).
- Source buttons open the reported HTTPS release pages by explicit user action; no automatic archive downloads, installs, removals, launches or backups are implemented in Dev3.
- The same existing banana yellow, charcoal, electric blue and green palette is reused for status icons, headings and links. No rebranding.
- Existing **1630 × 1060** screen-aware startup, responsive 2×2 cards on compact displays, sidebar, VR System, game dashboards, and all original installation functionality are preserved.

## Cyberpunk demo state (live read-only check during implementation)

- **4 updates available**: Cyber Engine Tweaks, Input Loader, Codeware and Visual Holsters.
- **9 up to date**: shown only when expanded.
- **1 needs review**: Visible Bullets (archive 2.31 versus Nexus 2.5; the version sequence cannot establish whether it is safely up to date or outdated).
- **1 install later**: CyberpunkVR Port, explicitly tagged phase 2 by the existing recipe. Its installation still follows the existing 14-mod first-run workflow; Dev3 does not change dependency policy.
- All 15 entries were displayed in the update tab with no duplicates. Changing games clears stale rows and uses each selected game's own returned results.

## Safeguards / acceptance requirements

- The test window uses a private copy of Hub's saved state, existing Nexus key **by file path**, and separate XDG config/cache/data.
- **No game installations, mod archives, save files, rollback data, or active OpenXR runtime changed** during development.
- The released Hub 0.5.4 and Dev1/Dev2 worktrees remain untouched. No source files from either branch were overwritten.
- A "Refresh update status" action only performs an already-supported read-only version query. It neither downloads nor installs.
- Normal Qt checks for missing sources, unrecognized versions, offline errors, and Nexus-key failures must **not** label a mod current.
- The full automated test suite, native Qt screenshots, responsive-layout tests, and user KDE review must pass before Dev3 is approved.

## Dev3 desktop acceptance checklist

- [ ] New Mod updates tab appears for the selected game, with the number of available updates.
- [ ] Cyberpunk shows four update rows with installed/latest version columns.
- [ ] The nine Up to date mods start collapsed and expand/collapse correctly.
- [ ] Visible Bullets appears under Needs review (not Up to date).
- [ ] CyberpunkVR Port appears under Install later (not falsely out of date).
- [ ] Open source buttons open the expected official mod/release pages.
- [ ] Refresh update status only checks versions and does not install or delete anything.
- [ ] Selecting Valheim, Fatekeeper and other games shows their own update results, never Cyberpunk's.
- [ ] Setup guide is cleaner, but installation instructions, Compatibility profile, Controller bindings and advanced tools remain accessible.
- [ ] The window still opens naturally around 1630 × 1060 and resizes without clipping or overlapping the mod tables.
- [ ] Original banana yellow, charcoal, cyan and green brand colors are preserved.
- [ ] User confirms PASS after KDE visual review.

## Next roadmap

Dev4 is the separate guided installation and selectable download-library milestone. Dev5 will address archive retention, mod version history, safe rollback, and named working configurations. Neither exists in Dev3.

## Automated verification and desktop preview (2026-11-20)

- **665 unit/regression test cases**, of which **664 passed and 1 was skipped**, using Qt offscreen.
- Real Hub update worker + private copied Hub-state + existing Nexus API configuration: **41/41 read-only Qt preview checks passed**.
- Real Cyberpunk records displayed **four updates, nine current, one review, one phase-2 install later**. No extra Nexus requests are made when just switching tabs.
- Structured version metadata was added to the checker results without changing which releases are considered current. The normal HTML guide remains unchanged unless the GUI explicitly requests compact output.
- Mod source links use explicit user interaction and validated HTTPS URLs; tests stub actual browser launching.
- All source fields, summary counts, group expansion, status colors, game switching, and the original **1630 × 1060** opening size passed Qt tests.
- Tested opening the nine-row **Up to date** list at both **1630 × 1060** and **920 × 600** without forced window growth or outer horizontal scrolling.
- The final screenshots are local/private QA captures in `~/.cache/nannersvrhub-055-dev3-preview.png` and `~/.cache/nannersvrhub-055-dev3-mod-tab.png`; they were not bundled with the program.
- Released NAnnersVRhub 0.5.4, Dev1, Dev2, game files, mods, saves, OpenXR runtime and previously installed archives remain unchanged.

**Manual KDE checklist above is not yet signed off.**
