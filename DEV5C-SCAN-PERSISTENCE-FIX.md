# Dev5C Fix: Saved archive scans survive development updates

Status: Implemented and tested; KDE desktop acceptance pending.
Base commit: Dev5C 22f06f0.
Scope: Development previews ONLY; released Hub and live game/mod files unchanged.

## Root cause

Each development milestone used a different private VRHUB_STATE folder, so
the Archive Scan feature did save each game's results, but a new milestone
read a different empty location. The old private results still existed:

- Dev5B1 saved scans: 8 game IDs.
- Dev5B2 saved scans: 9 game IDs.
- Dev5C saved scans: 6 game IDs.

## Fix: one stable isolated development-preview store

The KDE --desktop preview now reuses:

    ~/.local/share/nannersvrhub-development-preview/

This preview-only directory contains:

- state.json: private snapshot of existing development Hub state
- archive-scan-snapshots.json: restored scans for all nine game IDs
- download-folders.json: prior manually chosen folder preferences
- table-column-layouts.json: previously adjusted spreadsheet widths
- config/, cache/, data/: separate from the released Hub

Preview startup activates this stable directory BEFORE GUI imports,
rather than creating a different VRHUB_STATE with every development version.
The --verify automated GUI tests continue to use caller-supplied isolated
data; they NEVER rewrite the human preview's real saved scan timestamps.

### Migration policy

The one-time migration reads only the prior versioned private dev cache
folders. It validates the existing scan JSON schema and all referenced
archive paths. For every game it selects the newest saved scan whose
archive folder matches the effective user-selected preference, preserving
manually configured per-game overrides. It retains original timestamps
and historical status labels, rather than running a new scan.

Files are staged and published with no-overwrite atomic hard links.
Older preview files are NEVER modified or removed. A corrupt or
symlinked source causes a safe stop; nothing is overwritten. Once
migrated, later preview startups reuse the stable result and never
import stale historical copies again.

The released Hub data directory (normally ~/.local/share/vrhub) and
Steam, Heroic, OpenXR, game files, mods and saves remain unchanged.

### Actual data restored

Nine game IDs are present and each matches its selected archive folder:

- cyberpunk-2077 (original custom Cyberpunk-2077 folder, eight files scanned)
- doom-2016-gog
- elden-ring
- fatekeeper
- hogwarts-legacy
- ready-or-not
- skyrim-vr-mgo
- subnautica
- valheim

The original migration sources and released Hub state were hashed before
and after; all remained byte-for-byte identical.

The Downloads / Install Plan now shows a small visible indicator:
"Saved archive scans: 9 game profiles · Historical results retained across Hub updates."

Each game also shows its ORIGINAL Saved scan timestamp. An archive that
has changed since the historical scan is blocked until a manual rescan;
a saved result is NOT installation authorization or proof of VR readiness.

## Verified behavior

- Thirteen dedicated tests cover nine-game merge, retention of folder
  preferences, newest matching snapshot, idempotent reboots, preserving
  later manual scans, corrupt/symlink data refusal, and privacy.
- Direct Qt startup against ACTUAL recovered stable data restored
  nine of nine game pages WITHOUT scanning again.
- The restored saved-history file checksum stayed unchanged through
  the nine-game UI replay.
- Full regression and GUI checks are run separately with disposable
  private test data before human KDE review.

## Desktop acceptance checklist

- [ ] Dev5C opens at about 1630 x 1060 with approved styling.
- [ ] Saved archive scans: 9 game profiles appears in Downloads tab.
- [ ] All nine games immediately display their Saved scan history.
- [ ] Switching between games and back retains scan timestamps.
- [ ] Cyberpunk's per-game archive folder is preserved.
- [ ] A manual Scan local archives refreshes ONLY the selected game's
      historical record; other game scans stay saved.
- [ ] Closing and reopening the preview does not clear saved scans.
- [ ] Mod Updates, banners, install safety review and resizable columns
      still behave correctly.
- [ ] No actual download, mod installation, save edits or release Hub
      changes occur.

## Channel separation

This repair addresses DEVELOPMENT PREVIEW continuity. The released Hub
already uses a stable user directory, separate from the preview. It
does not automatically import private preview results into production.
Any future cross-channel import must be separately authorized.


## Verified checkpoint — 2026-11-20

- Full inherited regression: 837 tests, 836 passed, 1 skipped.
- Dev5C isolated GUI preview: 88 / 88 checks passed.
- New cross-development migration tests: 13 / 13 passed.
- Real restored snapshot replay: all nine game profiles displayed their
  historical saved scan on first visit, without invoking a new scan.
- The shared snapshot file was byte-for-byte unchanged after that replay
  and remained complete through the full automated GUI regression.
- The archive source files and released Hub data were unchanged.
- Desktop human acceptance remains pending; no live third-party downloads,
  archive installations, game launches or saved-game changes were performed.
