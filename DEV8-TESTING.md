# NAnnersVRhub 0.5.0-dev8 testing

Dev8 is the report-clarity and regression-review step before 0.5.0-rc1. It is
still a development build. No new live gameplay results are inferred from tests.

## Extract and run in fish

```fish
unzip -n ~/Downloads/NAnnersVRhub-0.5.0-dev8-source.zip -d ~/Downloads
and cd ~/Downloads/NAnnersVRhub-0.5.0-dev8
and python -m vrhub.gui
```

Use the existing PySide6 installation. No new runtime dependency is needed.

## Final desktop report check

1. Open VR System. Scanned/live times should now use your computer's local
   timezone and 24-hour clock, with a zone label such as PDT. For example,
   `2026-10-18T23:43:28.596274+00:00` displays as
   `2026-10-18 16:43:28 PDT` on a Los Angeles system.
2. Open Games -> Fatekeeper -> Compatibility profile. The sampled time, saved
   test time and history list should use that same presentation. The test's
   historical date/result/notes stay intact; earlier records are preserved.
3. Open Create support report. The fixed panel shows the captured local time
   and age. The timer only updates the age label; it does not recollect evidence.
4. With JSON selected, uncheck Include log excerpts. The visible indicator must
   say **JSON export · Log excerpts: OMITTED**. The preview's export option must
   read `"include_log_excerpts": false`, and finding excerpt lists must be empty.
5. Last matching log-entry metadata should remain available without excerpts.
   UEVR lines such as `[2026-10-18 16:11:14.485]` have no timezone: readable
   output explicitly says **timezone not recorded**. A log without timestamps
   says unknown; it does not reuse file modification time.
6. Copy and save the excerpt-free JSON under a new filename. The proposed name
   includes local time/zone and `-no-excerpts`. Existing destinations are still
   preserved. The copied/saved data must match the preview, including the false
   excerpt option and empty excerpt lists.
7. Close the game if desired, then press **Collect new snapshot**. A new capture
   time should appear. Saving alone does not recollect; a closed game may still
   have an old log and a recorded gameplay test. No running-game verdict is added.
8. Switch to Text report: local times and the captured-snapshot explanation
   should appear. JSON retains its original ISO source timestamps (UTC for scan
   and collection fields). Changing format/options does not change capture time.

The last-occurrence field means the last matching line in the inspected tail,
not a chronologically sorted maximum across the whole log. Earlier/truncated
data, timezone-less timestamps, resets and missing timestamps limit comparisons.
Dev8 does not mark an error active/resolved or prove a workaround's root cause.

## Four-game regression review

Use existing installs and working settings. Configuration checks and reports
can be reviewed without launching; a gameplay claim requires an explicit test.

| Workflow | Review |
| --- | --- |
| Skyrim VR / MGO | Correct MO2 shortcut/prefix/Proton policy; enabled XR or Unleashed adapter folder; disabled recognized VR Performance Kit variants; existing local history |
| Fatekeeper | Prefix/injector/profile inventories; OpenXR guidance; 2D Screen Mode off and Insert overlay workaround; saved local success remains separate from historical validation failures |
| Ready or Not | Recorded VRO package inventory; DirectX 11 and mission U/Home guidance; missing automatic log path stays unverified |
| Cyberpunk | All workflow phases/inventories; documented panel/menu limitations; pose/validation findings and latest local test remain separate |

The complete unit suite covers positive/negative fixture checks for these four
workflows. Host connection telemetry still does not automatically verify
controller input. No launch/install/profile code or recipe configuration is
changed in dev8.

## JSON compatibility

Host schema remains 2; compatibility/log/support schemas remain 1. Existing
timestamps and history storage are unchanged. Log finding dictionaries gain an
additive `last_occurrence` object: `tail_line`, raw `timestamp` (or null), and
`timezone_recorded` (true/false/null). It is retained by excerpt-free exports.
No timestamp is created from file modification time or a guessed log timezone.

## Existing checkout

Choose one patch:

- `dev8-from-dev7.patch`: incremental from delivered dev7 (b9492cc).
- `dev8.patch`: cumulative from clean v0.4.0 (2e320ac).

```fish
git status --short
git apply --check ~/Downloads/NAnnersVRhub-0.5.0-dev8/dev8-from-dev7.patch
git apply ~/Downloads/NAnnersVRhub-0.5.0-dev8/dev8-from-dev7.patch
python -m unittest discover -s tests -v
python -m vrhub.gui
```

Preserve unrelated work. If the check fails, stop and share the error. Do not
apply both patches. The extracted source can be tested directly.

## Validation

209 unit tests pass, including 17 new time/log-presentation tests covering the
reported UTC-to-PDT conversion, winter/summer and repeated-hour DST behavior,
date rollover, a non-US system timezone, unknown/malformed timestamps, age and
safe filenames, last matching line metadata, excerpt omission and unchanged
JSON/history data. Existing tests cover all four recipe workflows and exports.

Qt offscreen checks pass for local labels, captured-time/age persistence,
effective export indicators, false excerpt flags in preview/copy/saved JSON,
retained last-occurrence metadata, recollection, manual/automatic logs,
cancellation, existing-file preservation, partial sources, safe worker close,
and unchanged history/install state. The dialog is visually reviewed before
delivery. Desktop checks above remain the user's final confirmation.
