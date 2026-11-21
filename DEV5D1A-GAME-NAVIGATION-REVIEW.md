# NAnnersVRhub 0.5.5-dev5D1-A — Game Page Navigation Foundation

Status: Implemented and offline-verified. KDE desktop acceptance pending.

Approved baseline: Dev5C3a c06507e.
Isolated worktree: ~/Projects/NAnnersVRhub-0.5.5-dev5d1a
Branch: dev/0.5.5-game-nav-foundation

## Implemented

The game page now has these seven icon-and-label tabs in order:

1. Overview — existing game dashboard, launch/preflight, collapsible detailed library and advanced controls.
2. Mod Updates — existing categorized read-only update list, refresh control and dynamic count in tab label.
3. Install / Update — existing Guided Downloads / Install Plan; saved archive scans and resizable tables unchanged.
4. Rollback — existing guarded mod uninstall and UEVR restore controls, plus a read-only recovery-record explanation. A record is NOT treated as evidence of verified recoverability.
5. Compatibility — the original Compatibility profile: OpenXR/runtime and Proton/adapter policy, local checks, dated gameplay evidence, workarounds, test history and support reports. It is not the installable UEVR profile.
6. Controller Bindings — existing native per-game binding guide.
7. Setup Guide — existing HTML setup guide.

Game banner and artwork remain accessible across tabs. The selected tab uses the original yellow #FFD21A; hover uses #23B7FF. Icons use KDE theme with Qt fallback. Horizontal tab overflow is contained within the tab strip; the complete game page does not require horizontal scrolling at narrow sizes.

The advanced actions retained on Overview will be consolidated in Dev5D1-B. This step is navigation only, not a completed button cleanup or archive-first installer design.

## Preserved safety

- Dev5C2 Cyberpunk backups and legacy recovery guards untouched.
- Dev5C3 persistent UEVR whole-directory backups, checksum restore checks and closed live execution gate untouched.
- Original installer, game launch, updater, archive verification and recovery handlers untouched.
- Original Dev5C3a checkpoint and released 0.5.4 Hub unchanged.
- No real game, save, ZIP, mod, Proton prefix or installed UEVR profile modified.
- All nine previously saved per-game archive scan snapshots retained.
- Automated preview runs use isolated Hub state, config, and cache copies.
- Preview disables game launch, installs, removes, restores and downloads.

## Automated verification

Final full regression: **904 run; 903 passed; 1 skipped**.
Fresh native KDE preview: **110 of 110 checks passed**.
The narrow-window horizontal-scroll regression was fixed and retested.

## Desktop acceptance checklist

- [ ] Dev5D1a preview opens at the preferred KDE size, near 1630 x 1060.
- [ ] Seven icon tabs appear in the specified order.
- [ ] Overview retains banner, status cards, Launch Game, Preflight and existing optional controls.
- [ ] Active tab is yellow; non-selected tabs dark with blue hover accent.
- [ ] Mod Updates retains read-only version groups and update counts.
- [ ] Install / Update retains ZIP inventory, saved scans and draggable columns.
- [ ] Rollback shows guarded removal and restoration actions, with accurate legacy warnings.
- [ ] Compatibility still displays its original local evaluation and dated gameplay evidence, plus Refresh Compatibility, Record Live Test, Test History and reports.
- [ ] Controller Bindings and Setup Guide retain their original content.
- [ ] Narrow/resized windows retain accessible tabs with no full-page horizontal scrolling.
- [ ] Switching games and VR System preserves navigation, without modifying data.
- [ ] User approves the new navigation before Dev5D1-B.

## Deferred

Dev5D1-B: button consolidation and advanced-menu organization.
Dev5D1-C: visual polish and final icons/spacing after user KDE review.
Dev5D2: archive-first dependency checklist; retain all internal ZIP safety checks.

No live installer or profile recovery enablement is authorized by this UI checkpoint.
