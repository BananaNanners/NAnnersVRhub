# Dev5C follow-up — Human-readable installation sizes

Status: Implemented and verified; KDE desktop acceptance pending.

## User feedback

Raw byte totals in the installation safety review were difficult to interpret. Display sizes are now formatted as B, KB, MB or GB using decimal units (1 MB = 1,000,000 bytes; 1 GB = 1,000,000,000 bytes). Trailing zeros are removed, e.g. **18.6 MB**, **24.5 MB**, **2.5 GB**.

## Updated UI

- The installation review **overview** displays the original-file backup estimate in KB / MB / GB.
- The table's **Existing size** column displays the individual existing file sizes in the same format.
- The review notes' **Original backup size estimate** uses the same formatter.
- Hover over the backup overview or an existing file's size cell for the **exact raw byte count** when precise inspection is needed.
- Missing files still show **Not present**; sizes below 1 KB show their precise number of bytes.
- Exact integer byte counts, fingerprints, archive hashes, safety checks, storage limits and backup calculations are **unchanged**. This is a display-only change.
- No archive downloads, installations or game-file writes are performed by the preview.

## Tests

- Format boundary tests cover B, KB, MB and GB.
- Qt checks cover MB/GB display in both overview and table, exact bytes on hover, and preservation of original numeric backup values.
- Full Qt-offscreen regression: **840 tests run, 839 passed, 1 skipped**.
- Read-only GUI preview: **89/89 checks passed**, including a synthetic **18.6 MB** example.
- The stable development-preview store still has **all nine saved game scans**.
- The Dev5C installation confirmation remains disabled in preview.

## KDE acceptance checklist

- [ ] Open **Review installation** and confirm the backup estimate is easy to read.
- [ ] The **Existing size** column uses KB, MB or GB instead of long numbers.
- [ ] Hover over the backup overview and a file-size cell to see exact bytes.
- [ ] Scroll and resize columns normally.
- [ ] The three safety acknowledgments and disabled preview Install button still behave properly.
- [ ] Saved scans for the nine games remain present after restarting Dev5C.

This Dev5C polish checkpoint is independent of any future installer rollback enhancements.
