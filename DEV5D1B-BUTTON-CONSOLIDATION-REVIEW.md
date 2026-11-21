# NAnnersVRhub 0.5.5-dev5D1-B — Button Consolidation

**Status:** Offline implementation complete; user KDE desktop acceptance pending.

**Approved baseline:** Dev5D1-A commit e767622.
**Isolated branch:** dev/0.5.5-button-consolidation
**Worktree:** ~/Projects/NAnnersVRhub-0.5.5-dev5d1b

## Purpose

Simplify game-page controls while keeping all previously supported actions, original yellow-and-blue branding, seven-tab navigation, and all game safety gates. This milestone reorganizes UI access only; it does NOT redesign or enable the installer or UEVR profile restoration.

## Changes

- **Overview:** show only Launch Game and Preflight as prominent actions. Retain factual status cards, artwork and expandable detailed library. A relocated Refresh library control is available within the expanded detailed-library panel.
- **Mod Updates:** reuse the existing native Refresh update status button; remove the duplicate Overview update button and its redundant signal/state wiring. Move Mark as up to date and Nexus API key into collapsed More update tools.
- **Install / Update:** keep the guided ZIP archive checklist, Scan local archives, Review installation, verified downloads and existing safeguards. Replace four always-visible folder buttons with one Archive folder menu containing the same original controls. Put existing manual mod, UEVR profile, archive inspection, verification and DOOM-specific installation tools into a collapsed More installation tools group.
- **Compatibility:** preserve the original runtime/Proton/OpenXR configuration report, gameplay evidence and direct core controls. Move secondary launch, diagnostic and DOOM bridge tools into collapsed More compatibility tools.
- **Rollback:** preserve guarded mod removal and verified UEVR profile restore controls. Move development-only DOOM save recovery here, still gated behind the preexisting development-tools authorization. Hide irrelevant Remove profile control for recipes with no UEVR profile step.
- **Setup Guide / Controller Bindings:** behavior and content unchanged.
- **Responsive layout:** quick-action widget supports fewer buttons and compact stacking; archive-folder toolbar supports its two visible controls. No page-wide horizontal scrolling is introduced.

## Safety invariants

- No game, mod, archive, save, Steam/Heroic prefix, or real UEVR profile changed.
- Approved Dev5D1-A and Dev5C3 checkpoints remain intact.
- Dev5C2 Cyberpunk persistent original-file backups and recovery restrictions remain untouched.
- Dev5C3 UEVR whole-directory backup, SHA-256 restoration validation and closed mechanical live-execution gate remain untouched.
- Existing installer and download worker behavior is preserved. The folder dropdown mirrors each original button's enabled status and cannot invoke disabled operations.
- Archive folder controls are disabled during scanning and during a verified download.
- All nine private per-game saved archive scan snapshots are preserved.
- The GUI preview runs with private Hub state and disables all live installers, restoration, game launch, downloader and app-update operations.

## Verification

- Static Python syntax checks: PASS.
- Full regression suite: **915 tests executed, 914 passed, 1 skipped**.
- New tests cover button ownership, single update refresh, collapsed controls, folder-menu callback continuity, disabled actions, busy scans, and irrelevant profile restore controls.
- Isolated read-only KDE preview: **122 of 122 checks passed**.
- The final preview uses the correct Dev5D1b identity.
- Production Hub files were not modified.

## KDE desktop acceptance checklist

- [ ] Dev5D1b PREVIEW opens at natural 1630 x 1060 KDE window size.
- [ ] Overview shows game banner, status cards, Launch Game and Preflight, without duplicate update/install actions.
- [ ] Expand Detailed library table: spreadsheet-style column resizing and Refresh library remain accessible.
- [ ] Mod Updates has only one Refresh update status control and a collapsed More update tools section.
- [ ] Install / Update has Archive folder and Scan local archives as the compact folder row.
- [ ] Archive folder menu offers Choose game folder, Choose default folder, Use default folder, Auto-detect default.
- [ ] Saved archive scans, backup warnings and the existing ZIP dependency table appear correctly.
- [ ] More installation tools opens and retains original manual / UEVR / inspect / verify options without enabling live installation.
- [ ] Compatibility keeps original local and dated gameplay evidence, test history and reports; extra tools are grouped.
- [ ] Rollback retains safety warnings and relevant controls; no irrelevant Remove profile for a game without a profile step.
- [ ] All seven tabs work, and controls remain readable when resizing the window.
- [ ] Switching games and VR System works. Production files and saved data remain unchanged.
- [ ] Explicit user acceptance is received before Dev5D1-C.

## Deferred

- **Dev5D1-C:** final visual icon/spacing polish after acceptance.
- **Dev5D2:** ZIP-first package verification and archive-level install review, without weakening internal path and backup checks.
- **Future live-execution validation:** UEVR profile install/restore remains mechanically blocked regardless of Dev5D1-B GUI approval.

This checkpoint is a GUI consolidation, not an approval of live installers or recovery.
