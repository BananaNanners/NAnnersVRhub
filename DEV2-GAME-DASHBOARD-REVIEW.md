# NAnnersVRhub 0.5.5-dev2 — Game Dashboards

**Status:** Development implementation finished for KDE visual review, user acceptance PENDING. Branch `dev/0.5.5-game-dashboards` begins at the approved Dev1 commit `8375d14`. Released `main` 0.5.4 and Dev1 worktree remain unchanged.

## Scope and implementation

- Added `vrhub/dashboard_ui.py`: an original, reusable four-card game overview based on existing authoritative Hub state:
  - **Game install** — detected or missing from the configured Steam/Heroic store; never claimed as a gameplay pass.
  - **Mod setup** — exact recorded on-disk verification, including missing required components versus later-stage optional components.
  - **Mod updates** — reported current, outdated, needs-review, and not-installed counts. Empty/unfetched responses do not claim updates are current.
  - **VR preflight** — Not run until the user explicitly performs a preflight. A passing preflight says **Local checks passed**, not VR Ready.
- Reused the same Dev1 left game library, nine recipes, Games/VR System sidebar, quick actions, advanced action drawer, original Setup guide, Compatibility profile, and Controller bindings.
- Enlarged the existing game banner, adding an original brand-colored sci-fi visual treatment using the existing yellow, electric blue, charcoal and off-white palette. When an installed Steam game has `~/.local/share/Steam/appcache/librarycache/<appid>/library_hero.jpg` or `.png`, use that user-local cache file for personal display. **Never download, bundle, or redistribute artwork.** Missing artwork renders the original fallback instead.
- No added dependencies, download manager, extraction, mod removal, game launching, new live scanning, automatic preflights or rollback.
- Wired the preflight summary to the existing explicit Preflight action only. Preflight records are cleared by a new refresh, since installed mods/runtime conditions could change.
- Continued to respect the Cyberpunk update fix from the earlier development branch. It still identifies all 15 tracked Nexus mods independently; no new installation/version-policy decisions were made.

## Validation and safety

- Targeted Qt/model/dashboard tests include truthful installation status, required-versus-later mod classification, Nexus-version uncertainty, missing game, no update result, explicit-versus-not-run preflight, game selection, local artwork fallback, and **1200×750 window layout**.
- Full existing Hub regression suite plus Dev2 tests must pass before user acceptance.
- Read-only manual preview `tests/manual_launcher_dev2_preview.py` uses the existing private test-state copy and the existing Nexus API key *by path*, disables all actions that would install, remove, launch games or modify Hub applications, and captures the rendered Qt window for review.
- Device VR/system settings, game files and save data are never touched for this UI milestone.
- A picture of game artwork in previous concept art is an illustrative target, not evidence that third-party art is packaged in this release.
- **Steam/OpenXR local detection, Preflight, and historical headset tests are separate kinds of evidence.** Do not label any title VR Ready unless actual supported live test evidence is valid and specifically available.

## Acceptance checklist (user on KDE)

1. **Dev2 game dashboard preview** opens and retains original BananaNanners branding.
2. Game hero title and original visual fallback update when changing games.
3. Four cards show actual data and agree with the existing Setup guide/Mod status table.
4. Cyberpunk shows its current recorded mods (e.g., 14/15) and current Nexus update count, with VR preflight marked Not run.
5. Changing to Valheim/Fatekeeper/DOOM updates all four cards and never reuses Cyberpunk statuses.
6. Games/VR System navigation, detailed library table, advanced tools, compatibility and controller bindings remain accessible.
7. The entire layout fits comfortably at the user's KDE scale; review on both main and secondary displays if relevant.
8. The test build cannot modify installed mods or saves, and the released 0.5.4 hub remains independently available.

**Next milestone:** Dev3 dedicated structured Mod Updates tab; download folder selection in Dev4; per-mod rollback in Dev5. User input may refine visual layout before Dev3 begins.

## November 20 follow-up: resizable game launcher and user checklist

User liked the new cards but could not restore/resize the window; at maximum size the cards became excessively wide. Also requested an explicit **checkbox-style desktop acceptance checklist for each future dev**.

**Root cause verified in real Qt geometry:** old minimum window height ~1041 and min-size hint 824×1063; resize(1200,750) actually yielded 1200×1063. A long Setup guide was constraining the root shell. Fixed with an independently scrollable Games page, centered **1420px content cap**, two-column card reflow below 980px page width, and two-column quick-action reflow below 840px. The preview now opens restored at 1120×720 rather than 1450×880.

During visual review, an additional **first-resize overlap bug** was discovered: the QGrid reflow updated size hints but retained the previous one-row widget height until a second resize. Both cards and quick-action rows now immediately set their new minimum heights and invalidate geometry on reflow. A dedicated regression test verifies the children fit inside the parent on the **first** resize in both directions.

**Automated results:** 644 total test cases, **643 passed, 1 skipped**, including nine responsive layout tests. Read-only GUI preview **29/29** checks passed, including real 920×600 geometry, no horizontal scroll, visible VR System control, compact card/action columns, maximized content cap, and restored 1120×720 layout. Reviewed rendered image confirms no overlap or clipping.

**Human KDE acceptance is still pending.** The new project checklist `DEV2-RESIZE-ACCEPTANCE.md` should serve as the pattern for future devs. No install, game, runtime or release files changed.
