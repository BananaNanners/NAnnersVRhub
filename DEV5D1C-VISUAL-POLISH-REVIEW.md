# NAnnersVRhub 0.5.5-dev5D1-C — Visual Polish

**Status:** Implemented and verified offline. User KDE desktop acceptance pending.

**Approved base:** Dev5D1-B game launch actions checkpoint `c570a02`.
**Isolated worktree:** `~/Projects/NAnnersVRhub-0.5.5-dev5d1c`
**Branch:** `dev/0.5.5-visual-polish`

## Scope

Dev5D1-C changes **visual presentation only**, not the working logic of the Hub. All original BananaNanners branding remains: banana yellow `#FFD21A`, electric blue `#23B7FF`, charcoal `#0A0D10`.

### Visual changes

1. **Seven-tab navigation** — More consistent tab spacing, boundaries, typography and blue hover treatment. KDE theme icons retain their original symbols; the selected tab icon is dark on yellow for contrast and inactive icons are muted. Icon appearance refreshes when changing tabs, without replacing pages, names or handlers.
2. **Overview Launch Tools** — A compact dark-blue outlined section and readable blue heading groups Steam launch options, the UEVR injector, Skyrim MO2, and DOOM VR/bridge test as already approved. Secondary launch controls receive consistent subtle styling. Game-specific visibility and the actual action callbacks are unchanged.
3. **Expand/collapse controls** — Overview library details, Update tools, Installation tools and Compatibility tools receive consistent readable text, hover and checked-state styling. Expansion functionality is unchanged.
4. **Compatibility** — Consistent internal margins/spacing around the original compatibility report, runtime settings, live-test evidence and diagnostics. No evaluation/reporting logic changed.
5. **Readability and keyboard focus** — Slightly larger explanation text in Mod Updates and Install / Update, and clear button focus borders. No new text fields, menus or installation actions.

## Safety and preservation

- No changes to `vrhub/hub.py`, `vrhub/handlers.py`, `vrhub/profile_safety.py`, `vrhub/install_review.py`, `vrhub/downloads_gui.py`, `vrhub/compatibility.py` or `vrhub/download_planner.py`.
- Original DOOM Flat / DOOM VR / Test VR bridge and Skyrim VR / MO2 buttons remain wired to the original handlers. Visibility is context-sensitive; the visual work does not enable or initiate any action.
- Dev5C2 Cyberpunk persistent backup/recovery protection remains unchanged.
- Dev5C3 UEVR whole-directory backups, SHA-256 restoration checks and mechanical **closed live profile-execution gate** remain unchanged.
- The released Hub, installed games, VR setups, ZIP archives, Steam/Heroic prefixes and saves are untouched.
- Prior approved Dev5D1-B checkpoint `c570a02` and earlier branches remain unchanged.
- The KDE preview is **read-only**, with game launch, injection, bridge probe, installation, restoration and download operations disabled.
- All automated preview runs use isolated copies of private Hub state/config/cache.

### Separate saved-scan discrepancy

The shared development-preview store currently contains **one saved game archive scan**, while earlier milestones recorded nine. This discrepancy predates the Dev5D1-C changes. Dev5D1-C has not modified, reconstructed, overwritten or deleted those scan records. Investigate separately; do not claim scan persistence is restored on the basis of this UI approval.

## Automated verification

- Static Python syntax and Git whitespace checks: PASS.
- Full offline test suite: **931 run, 930 passed, one skipped**.
- Isolated Qt/KDE preview: **160/160 checks passed**.
- Extra Dev5D1-C tests validate exact retained brand colors, icon contrast through several tab changes, unchanged tab-widget identities, scoped action styling, disclosures, Compatibility report, and page-level horizontal scrolling at widths 850–1630.
- Seven tab screenshots plus DOOM/Skyrim action screenshots were captured and visually inspected.
- No real launch, UEVR profile modification, rollback or game change was executed.

## KDE desktop acceptance checklist

- [ ] Dev5D1-C preview opens non-maximized at the preferred **1630 × 1060**.
- [ ] Seven navigation tabs, original yellow active tab and dark icon-on-yellow contrast look right.
- [ ] Hovering inactive tabs and expandable sections shows the original electric-blue accent.
- [ ] DOOM Overview retains Launch DOOM (flat), Preflight, Launch DOOM VR and Test VR bridge.
- [ ] Skyrim Overview retains Launch Skyrim VR, Copy launch options and Launch MO2.
- [ ] Fatekeeper, Hogwarts and Cyberpunk Launch Tools still appear only when applicable.
- [ ] Launch Tools panel is compact, readable and visually distinct without taking over the dashboard.
- [ ] Mod Updates and Install / Update labels, buttons and help text are readable.
- [ ] Rollback, Compatibility, Controller Bindings and Setup Guide remain intact.
- [ ] Window resizing preserves navigation and avoids full-page horizontal scroll; tab overflow is handled inside the tab strip.
- [ ] Expanded advanced tool sections open and close without hiding content or resizing the main window unexpectedly.
- [ ] Live game, injector, bridge test, install and restore actions are disabled in the preview. No saved data modified.
- [ ] User approves the visual result before further development.

## Deferred

- Dev5D2: archive-first dependency checklist and package-level review (do not weaken ZIP path, verification, backup or recovery checks).
- Saved scan persistence investigation is a separate issue, not part of this visual-polish milestone.
- Live UEVR profile installation and restoration remain gated pending independent safety verification.

**UI approval does not authorize enabling real-world UEVR profile modification.**
