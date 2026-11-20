# NAnnersVRhub 0.5.5-dev4 — Game Artwork Manager

**Status:** Implementation ready for user KDE desktop acceptance. No release installation has been performed.

**Branch / worktree:** `dev/0.5.5-artwork-manager` — `~/Projects/NAnnersVRhub-0.5.5-dev4/`.

**Approved baseline:** Dev3 commit `64d94aa` on `dev/0.5.5-mod-updates`.

## New features

1. Each game has a visible **Artwork: [source]** label below its hero banner.
2. **Change banner…** accepts locally supplied JPG, JPEG, PNG, or WebP images, validates size/decoding, scales while keeping aspect ratio, and atomically saves a private PNG copy under `$XDG_DATA_HOME/nannersvrhub/artwork/<game-id>.png` (or `~/.local/share/nannersvrhub/artwork/` by default). **Only the Hub-owned copy changes**; the original image is never altered. 25 MB upload size limit; 45 megapixel decode limit.
3. **Restore default** removes only that game's Hub-owned custom image and goes back to automatically discovered Steam/Heroic artwork, or the original branded geometric fallback if none is cached. Even corrupted Hub-managed copies can be cleared.
4. Custom image per-game selection is persistent across application restarts, independent of tracked game installations, mods and saves; it never touches a Steam/Heroic folder.
5. Automatic read-only discovery: Steam custom grid override (if configured), Steam local `library_hero` (JPG/PNG/WebP) and header fallbacks, plus native and Flatpak Heroic locally cached game cover images. For Heroic/Epic the app identity is matched from Heroic's installed-game metadata rather than guessing the game ID.
6. Nothing is downloaded from online artwork APIs. If no local image is available, the original yellow/cyan geometric hero banner remains the fallback. Existing banner framing and scaling remain unchanged.
7. Original theme remains banana yellow `#FFD21A`, cyan `#23B7FF`, charcoal, green and red.
8. Dev1–Dev3 UI behavior, **1630 × 1060** default window, compact layout and responsive scrolling are preserved. Planned Downloads and Backups labels now point to Dev5 and Dev6.

## Existing local artwork discovered (read-only inspection)

| Game | Found source |
|---|---|
| Cyberpunk 2077 | Original NAnnersVRhub fallback |
| DOOM (2016) | Heroic local cover cache |
| Elden Ring | Steam library hero cache |
| Fatekeeper | Original fallback |
| Hogwarts Legacy | Heroic local cover cache |
| Ready or Not | Original fallback |
| Skyrim VR | Steam library hero cache |
| Subnautica | Steam library hero cache |
| Valheim | Original fallback |

The Hub does not claim that a cached image means a game is installed or VR-ready. The test preview must use isolated XDG settings and **only read** existing Steam/Heroic images; game scans and existing saved-state checks remain independent.

## Safety and testing

- Separate Dev4 Git worktree. Released NAnnersVRhub 0.5.4, approved Dev1/Dev2/Dev3 checkpoints and all installed games/mods/saves remain untouched.
- A private `~/.cache/nannersvrhub-055-dev4-state-20261120/` test state and XDG config/cache/data isolate the manual preview. **The preview's Change banner/Restore default buttons write only to that private test data folder** and can be safely exercised; no installed game or production Hub artwork preference is edited.
- Preview disables installation, uninstall, game launch, save recovery, Hub self-update and all other potentially mutating controls.
- No attempt is made to download or redistribute copyrighted game artwork. It remains user-cached and locally referenced, never bundled with the repository or GitHub release.
- Tests cover the original fallback, Steam and Heroic source detection, corrupted files, path traversal, format validation, import persistence, independent game choices, restore, and window resizing.
- Minor Dev3 issue noticed during visual QA fixed: stale Mod Updates source button widgets are cleared when switching games; regression test added.

## Dev4 KDE desktop acceptance checklist

- [ ] Window opens at the familiar comfortable 1630 × 1060 with the sidebar and status cards.
- [ ] The **Artwork** label shows the correct source for the selected game.
- [ ] Subnautica / Skyrim VR / Elden Ring show cached Steam artwork.
- [ ] Hogwarts Legacy and DOOM show the locally cached Heroic artwork.
- [ ] Games without artwork use the original branded geometric fallback.
- [ ] **Change banner…** accepts a JPG, PNG or WebP and displays it immediately.
- [ ] A selected custom banner persists when switching away and back and when reopening this same test preview.
- [ ] **Restore default** returns to the discovered local image or original fallback without changing the source image.
- [ ] All game dashboards and the Mod Updates tab remain accessible and have no leftover source buttons.
- [ ] Resizing and maximizing work, including compact width; no text or buttons overlap.
- [ ] No installed games, mods, saves, Steam/Heroic settings or production hub files are changed.
- [ ] User explicitly confirms Dev4 acceptance before the Dev5 downloads milestone starts.

## Verified implementation checkpoint (2026-11-20)

- Full test suite: **698 tests run, 697 passed, 1 skipped**.
- Real-data Qt GUI integration: **46/46 checks passed**, including source detection, no content-width regression, and 1630×1060 default.
- Actual local sources verified: 5/9 games can display Steam or Heroic cached art without any network requests; 4/9 use the original branded fallback until artwork is selected.
- The isolated preview's Heroic configuration points read-only at the native installed Heroic metadata so the Hogwarts detection indicator is accurate; the preview's XDG write paths remain private to \`~/.cache/nannersvrhub-055-dev4-state-20261120/\`.
- Local visual QA: Hogwarts Heroic art rendered correctly at 1630×1060. The previous Mod Updates stray source button was eliminated by clearing old rows before replacing table widgets, and a regression test was added.
- User review is still pending. Dev4 is **not** marked approved until the user checks the desktop window.

## Next milestone

**Dev5 — Guided Installation & Downloads.** Custom download folders, existing archive reuse, safe installation previews and actual downloads are kept separate from this artwork milestone. **Dev6 — Per-mod rollback** follows.
