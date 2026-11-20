# Dev5A follow-up — Spreadsheet-style resizable columns

**Status:** Implementation verified in Qt unit checks; waiting for user's KDE acceptance.

**Why:** In the user's screenshot, the expanded **Game** column takes disproportionate horizontal space while Game install, Mod, Profile and Updates values truncate; the Qt header separators could not be dragged. The Downloads and Mod Updates tables had the same fixed/stretch modes.

## Implementation

- Replaced hard-coded **Stretch/Fixed** column modes in the detailed game library, Downloads / Install Plan and Mod Updates with Qt **Interactive** section resizing.
- **Drag the separator between column header names** to resize, **double-click** a separator to fit the longest relevant text up to a sensible 720-pixel cap.
- Initial widths use balanced defaults and expand once to use the available table viewport, while still remaining individually adjustable. The game title no longer takes most of the horizontal space.
- Long content wraps after narrowing a column; rows expand up to a bounded height. All item values remain available as hover tooltips, and horizontal scrolling belongs to the table rather than forcing the entire app to expand.
- Each table remembers its own widths across game selections and launcher restarts in the Hub-owned `table-column-layouts.json` beside its state file. The user only writes settings by manually resizing a visible header; simply opening a new table doesn't write any preference.
- Settings are bounded, validated and atomically updated with a file lock. Invalid or symlinked existing preferences are preserved rather than overwritten. This data is purely presentation preference, never mod/game state.
- The detailed game library now shows a brief in-app hint explaining header drag and double-click.
- The 1630 × 1060 startup size, theme, existing game selection and install safety mechanisms are unchanged.
- The isolated Dev5A preview points to private state and presentation settings under `~/.cache/nannersvrhub-055-dev5-state-20261120/`. Released NAnnersVRhub 0.5.4, approved Dev1–Dev4 branches, mods/saves and production preferences remain untouched.
- This update implements **no automated downloads or new game installation actions**.

## Desktop acceptance checklist

- [ ] On the expanded detailed library table, **Game** is a sensible width beside Game install, Mod, Profile and Updates.
- [ ] Drag between the **Game** and **Game install** headers to change the first column's width.
- [ ] Double-click a column separator to fit its text.
- [ ] Shrink a column and verify text wraps or remains available on hover.
- [ ] Adjust **Mod** and **Updates** independently; widths stay after selecting another game or refreshing.
- [ ] Try the same resize behavior in **Downloads / Install Plan**, and confirm its table fills the space without a pale blank strip.
- [ ] Check **Mod updates**; its columns also resize.
- [ ] Close and reopen the isolated Dev5A preview: custom widths remain (the preview's own test settings only).
- [ ] Resize the main window to compact dimensions and back: sidebar and outer game page remain functional, no overlapping controls.
- [ ] User confirms the layout fix passes before Dev5B starts.

## Final checks — 2026-11-20

- Full Qt-offscreen suite: **741 tests run, 740 passed, 1 skipped**.
- Real NAnnersVRhub state and archive-library Qt preview: **60/60 GUI checks passed**, including responsive main window, all three interactive headers, isolated presentation preferences and balanced game title column.
- Mouse-event tests verified both dragging the separator and double-clicking the separator to fit text. Persisted widths survive reopening a table in a new widget, while separate game-library, download-plan and mod-update preferences remain independent.
- Reflow and cleanup tests confirm wrapped text, bounded row heights, safe deferred Qt timer deletion, valid preferences, and no accidental overwrite of corrupt/symlinked preferences.
- The preview remains read-only for game files, downloads, installers, launches and backups. Manual column-width choices write only to its private test XDG/Hub state.
- The change remains **pending user acceptance**; previous approved Dev4 baseline and released Hub stay untouched.
