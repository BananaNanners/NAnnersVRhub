# NAnnersVRhub 0.5.5-dev5B1 — Saved Per-Game Archive Scans

**Status: Implemented and automated checks passed; KDE desktop acceptance pending.**

**User-reported issue:** Scanning the local archive library in Cyberpunk, switching to another game, and returning discarded the previous scan. Dev5A stored only one `_last_plan`, and switching game selections erased that single value.

**Baseline:** Approved Dev5A `5f3bc2f` (including spreadsheet-style column resizing).
**New branch:** `dev/0.5.5-verified-downloads`, isolated worktree `~/Projects/NAnnersVRhub-0.5.5-dev5b/`.

## What changed

1. Each of the nine game profiles has an **independent scan snapshot**. Switching games and returning immediately restores that game's table and verification statuses without issuing another scan or changing archive files.
2. Successful user-requested scans are also persisted in a bounded, atomic, locked, private **Hub-owned JSON file** `archive-scan-snapshots.json` beside `VRHUB_STATE`, so closing and reopening the app also restores previous results.
3. A prominent blue **Saved scan: YYYY-MM-DD HH:MM (local time)** label is shown above the archive table. It explicitly describes the result as a **historical snapshot, not fresh verification** and recommends rescanning when archives are added, removed or updated.
4. Each selected candidate archive's file size, mtime nanoseconds, inode and device are saved when the scan completes. On a later visit, if the archive has been modified, removed, or replaced by a symlink, the previously positive result is no longer displayed as verified: the affected row becomes **Archive changed — rescan required** in red and its stale path cannot be inspected from that row. No claims about freshness are inferred from unobserved additions; the snapshot warning always remains.
5. **Scan local archives** still triggers a new read-only scan. Its successful result replaces the saved snapshot **for that game only**, without clearing other profiles' results.
6. Per-game folder changes discard that game's now-incompatible scan; global-folder changes invalidate only snapshots for games actually affected, leaving unchanged per-game overrides intact. The app never trusts results from a different selected folder.
7. If a scan finishes while another game is selected, it is filed under the **original game that started the worker**, never shown under the wrong game.
8. A corrupt or symlinked existing snapshot file is **preserved** rather than silently overwritten. Errors cannot trigger game-file changes.
9. The original 1630 × 1060 size, yellow/charcoal/cyan theme, Game Artwork Manager, per-column resizing, Mod Updates, installed game detection, and all Dev5A download-folder controls remain unchanged.

## Real archive verification

- Cyberpunk 2077: **15 possible filename/Nexus-ID matches**, all still marked for review; the later-stage CyberpunkVR Port remains phase 2.
- Valheim: **2 pinned SHA-256 verified archives**.
- Subnautica: **2 pinned SHA-256 verified archives**.
- These three saved profiles were restored by switching without rescanning. An entirely new Qt page instance also recovered Valheim's saved result from disk.
- Those checks were performed with the user's existing **read-only** VR-Mods library and a **private copy of Hub state**.

## Safety boundaries

- **No new downloads have been implemented or authorized in Dev5B1.** This is the first usability checkpoint of Dev5B; the network/download engine with source verification, user authorization, progress and failure controls remains the next stage, Dev5B2.
- No archives were extracted, downloaded, moved, overwritten or deleted; no game installation, game launch, mod update, rollback, save modification or production Hub configuration change was performed.
- The test preview's snapshot file lives under `~/.cache/nannersvrhub-055-dev5b-state-20261120/`, separately from the installed Hub's state. The test window keeps all existing mutating launch/installation controls disabled.
- No archive scan is an authorization to install. Actual downloads and installations will require their own approved safety review and explicit interaction.
- The user's released 0.5.4 Hub and approved Dev1–Dev5A worktrees remain untouched.

## Automated verification

- Qt offscreen full regression suite: **757 tests run; 756 passed, 1 skipped**.
- Isolated full KDE-style Qt integration: **71/71 checks passed** using the local archive library and separate saved-state copy.
- Dedicated tests cover per-game independence, game switching, persistence after reopening, folder invalidation, hashing/inspection status not overstated, scan-worker race, symlink replacement, deleted and modified files, malformed snapshot preservation, and isolation from Steam/Heroic game files.

## Dev5B1 KDE desktop acceptance checklist

- [ ] The new preview opens in the familiar launcher at approximately **1630 × 1060**.
- [ ] Cyberpunk's **Downloads / Install Plan** shows its saved scan timestamp and 15 possible archive matches.
- [ ] Switch to **Valheim**: its two SHA-256 verified packages and its own scan time are shown.
- [ ] Switch to **Subnautica**: its two SHA-256 verified packages and its own scan time are shown.
- [ ] Switch back to **Cyberpunk** without pressing Scan local archives: its 15 matches return, with the previously saved timestamp.
- [ ] Scan another game manually: it does not clear the earlier games' saved results.
- [ ] The notice clearly identifies results as a **historical snapshot**, not a freshly verified download.
- [ ] Existing spreadsheet-style resizing, artwork, Mod Updates, VR System and window size still behave normally.
- [ ] No downloads, installations or game-file changes occur during navigation.
- [ ] User explicitly approves Dev5B1 before continuing to Dev5B2.

## Planned next development

**Dev5B2 — user-authorized verified archive downloads.** This stage will address source URL allowlists, supported direct upstream files versus manual/Nexus login flows, expected SHA-256 pinning, progress, cancellation, retry, staging, and safety. Neither new live download nor mod install is part of Dev5B1.

## UI clarity follow-up — folder controls and hover descriptions

The user identified confusion between resetting the **default folder choice**
and resetting saved scans/verification. Dev5B1 now provides native Qt hover
tooltips for all five folder/scan actions and the read-only archive inspector.
The two folder-picker buttons use plain labels without trailing ellipses:

- **Choose default folder** opens the global archive-library folder picker.
- **Choose game folder** opens a per-game override picker.
- **Use default folder** removes the selected game's override.
- **Auto-detect folder** clears the global override and returns to automatic
  folder discovery; this is **not** a "clear saved scans" command. Only a change
  of effective folder invalidates affected game snapshots.
- **Scan local archives** explicitly scans files and refreshes this game's saved
  result; it does not download or install anything.

The existing scan-persistence and folder selection logic is unchanged. No
additional destructive "Clear scans" command was added. Hover descriptions
are read-only, and all preview settings remain isolated from production.

### Additional UI acceptance

- [ ] The folder picker buttons no longer show trailing ellipses.
- [ ] Hover over every control and see a helpful description of its actual behavior.
- [ ] **Auto-detect folder** clearly states that unchanged-folder scans persist.
- [ ] Existing Cyberpunk, Valheim and Subnautica snapshots still reappear on game switch.

## Compact hover descriptions and visible Auto-detect result

User screenshots revealed that Qt's previous long, unbroken tooltips stretched
almost the entire desktop width. Hover text is now limited to **two or three
short lines** (under 59 characters each), preserving native KDE/Qt tooltip
appearance without covering the window.

**Auto-detect default** is now explicitly scoped to the SHARED default
archive folder. The location display shows BOTH the current selected game
folder and the shared default, with a marker for auto-detection, manual shared
selection, or a per-game override. A dedicated inline result message explains
when the shared default was restored but a per-game override still takes
precedence, and directs the user to **Use default folder**. It also reports
when the shared default was already auto-detected, without unnecessarily
writing a settings file.

Archive results are not cleared when the effective folder is unchanged.
The selected game's existing override remains intact until the user chooses
**Use default folder**; resetting the shared default cannot silently
change another game's manually chosen folder. No destructive actions exist.

### Additional desktop acceptance

- [ ] Hover hints fit in compact multi-line boxes rather than spanning the screen.
- [ ] Set a custom game folder and click **Auto-detect default**: both folder paths remain visible, and the message explains the custom override is still active.
- [ ] Click **Use default folder**: the selected game returns to the shared default.
- [ ] With an unchanged effective folder, saved scans remain present.

### Verified follow-up checkpoint (2026-11-20)

- Native tooltips shortened to 2–3 deliberate lines, each at most 58 characters; test additionally checks rendered font metrics remain within 425 pixels per line.
- **Auto-detect default** resets only the shared default, not a game-specific override. The page explicitly shows the effective game folder and the shared default together, and a short feedback message explains what occurred and whether the game override still applies.
- **Use default folder** removes the game override so its effective path follows the shared default. Clicking Auto-detect with no custom shared default reports that no change was necessary and avoids writing settings.
- New desktop preview opens with the old detailed library table collapsed so all folder controls are visible.
- Complete regression: **762 tests run, 761 passed, 1 skipped**.
- Isolated real-library Qt verification: **75/75 checks passed**, including tooltip length and separate folder source displays.
- **KDE user acceptance of this follow-up is pending.** No new downloads, installs or game-file writes were enabled.
