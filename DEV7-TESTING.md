# NAnnersVRhub 0.5.0-dev7 testing

Dev7 adds one reviewable support report for a selected game. It includes dev6
fix1's error signatures and the confirmed Fatekeeper overlay workaround.

## Extract and launch

Run in fish after downloading the new ZIP:

```fish
unzip -n ~/Downloads/NAnnersVRhub-0.5.0-dev7-source.zip -d ~/Downloads
and cd ~/Downloads/NAnnersVRhub-0.5.0-dev7
and python -m vrhub.gui
```

Use the existing PySide6 installation. No new runtime dependency is needed.

## First desktop check

1. Open Games -> Fatekeeper -> Compatibility profile. Confirm your most recent
   saved test is still present; dev7 does not recreate or replace it.
2. Click **Create support report…**. Collection runs in the background and reads
   fresh sources rather than reusing the VR System tab's older scan.
3. Confirm the preview contains four sections: VR system, compatibility/current
   configuration, log evidence and latest local gameplay test. The last section
   includes the saved test's own date, notes/checks and historical setup findings.
4. Confirm the profile guidance says **2D Screen Mode OFF**, then close UEVR's
   in-game overlay using **Insert**. It distinguishes the overlay from the desktop
   injector window and notes the reported WayVR shortcut collision.
5. Leave **Replace this Linux home path with ~** checked. The current Linux home
   prefix should become `~` throughout the prepared report. Uncheck it to compare.
6. Uncheck **Include log excerpts**. Counts, explanations, dates and suggested
   actions remain; the excerpt lines disappear. Changing these options does not
   recollect the snapshot or change its timestamps.
7. Click **Copy report** and paste it for review. The copied content is the same
   text as the preview. Switch to **JSON report**, then copy or save it as JSON.
8. **Save report…** creates a new private file. Cancel creates nothing. If a name
   already exists, select a new name; existing files are preserved. Review the
   saved content before sharing it.
9. Use **Refresh snapshot** to collect again. Explicit **Choose log files…**
   selection replaces automatic discovery and refreshes all four sections;
   **Use expected log** restores automatic discovery. Canceling the file picker
   keeps the existing preview.

Repeat for Cyberpunk to confirm its latest local test, menu limitation and log
findings appear together. A recorded successful/partial gameplay test does not
erase errors in an older log or turn manual configuration checks into automatic
passes. Log findings do not change the saved test outcome.

## Scope, dates and incomplete evidence

- All source sections are sampled sequentially. The report is not an atomic
  measurement of one gameplay session; section and native source timestamps are
  retained separately. File modification time still does not identify a session.
- COMPLETE means all four collectors returned usable data, including explicit
  missing/unverified results. It does not mean a game is ready, a log exists, a
  test was performed, or VR currently works. PARTIAL means at least one collector
  failed; other sections remain available, with a visible error for that source.
- An empty local history stays empty. Bundled recipe references are not imported
  as local tests. Damaged history is reported and preserved, never silently reset.
- The selected game's latest test is included with its recorded setup snapshot;
  older local entries remain accessible through Test history. Other games' local
  histories are not exported.
- Compatibility JSON retains its existing local-test fields. The combined JSON
  also exposes a dedicated gameplay section drawn from that same history read;
  these describe the same record, not two independent tests. If compatibility
  collection fails, the gameplay collector attempts a separate history read.
- Log reads retain dev6's four-file, 512 KiB-per-file, line and excerpt limits.
  No full raw logs, arbitrary process command lines, entire environment or
  installer-state dump are added. Explicit logs must be associated with the
  selected game by the user; the report cannot verify that association.
- Home-path replacement is a convenience, not complete anonymization. Other
  users' paths, paths outside this Linux home, hardware/headset names, relevant
  environment values and personal information inside notes/excerpts may remain.
  Excerpt omission does not remove user-entered test notes or log source paths.
- Collection and preview perform no network request, automatic upload, saved
  report write, gameplay-history write or game/runtime configuration change.
  Copy uses the clipboard only when clicked; save writes only the chosen new
  report. The existing Hub update checker remains independent of this workflow.

## CLI

```fish
python -m vrhub.cli support-report fatekeeper
python -m vrhub.cli support-report cyberpunk-2077 --json --no-excerpts
python -m vrhub.cli support-report fatekeeper --output ~/Downloads/Fatekeeper-support-new.txt
python -m vrhub.cli support-report ready-or-not --file /path/to/log.txt --json --include-home-path
```

Without `--output`, the report is printed only. With it, the same content is
printed and saved. `--json` determines the file/content format; choose a matching
extension. Existing files (including symlinks) are never overwritten. A failed
save cleans the temporary file and returns an error.

Exit 0 means COMPLETE collection, even when host/configuration findings are NOT
READY or a log is missing. Exit 1 means PARTIAL collection, invalid input or a
save failure. A partial report is still printed unless saving itself failed.
These exit codes are collection availability, not gameplay success.

The combined JSON has its own schema version 1 with header metadata, collection
times/status, notice, four sections (availability/times/data/error), and export
options. Native scan/compatibility/log schemas and local history are unchanged.

## Existing checkout

Choose one patch:

- `dev7-from-dev6-fix1.patch`: incremental from delivered dev6-fix1 (0274c01).
- `dev7.patch`: cumulative from clean v0.4.0 (2e320ac).

From a matching checkout:

```fish
git status --short
git apply --check ~/Downloads/NAnnersVRhub-0.5.0-dev7/dev7-from-dev6-fix1.patch
git apply ~/Downloads/NAnnersVRhub-0.5.0-dev7/dev7-from-dev6-fix1.patch
python -m unittest discover -s tests -v
python -m vrhub.gui
```

Preserve unrelated local work. If the check fails, stop and share the error.
Do not apply both patches. The extracted source can be tested directly.

## Validation

192 unit tests pass, including 22 new support-report tests for separate evidence
and dates, selected-game/latest-result scope, fresh and immutable snapshots,
missing/failed/corrupt sources, recursive home-prefix replacement, excerpt
omission, literal text/JSON, non-mutating collection, private atomic saves,
existing-file preservation, CLI output/exit codes, and Fatekeeper guidance.

Qt offscreen checks cover the actual main-window modal route, text/JSON
preview-copy-save equality, options without recollection, manual/automatic logs,
picker/save cancellation, existing-file preservation, usable partial reports,
safe close during collection, and unchanged gameplay history/installer state.
The report dialog and main window were visually inspected. A real CLI collection
in the build environment also completed with explicitly missing/not-ready game
evidence. Desktop validation on the user's running setup remains the next step.
