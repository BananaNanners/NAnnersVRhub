# NAnnersVRhub 0.5.0-dev5 testing

Dev5 implements the first next-roadmap item: recording and reviewing local
user-reported live tests. Automated game-log diagnosis and the combined support
report remain later work.

## Run

Extract the ZIP in Downloads, then run in fish:

```fish
cd ~/Downloads/NAnnersVRhub-0.5.0-dev5
python -m unittest discover -s tests -v
python -m vrhub.gui
```

Use the existing PySide6 installation. No new dependency is needed on Linux.

## First local test record

1. Open Games -> Cyberpunk 2077 -> Compatibility profile.
2. Click **Record live test…**.
3. For the previously reported immersive result with disabled HUD panels, choose
   **Partial Success** to retain the limitations.
4. Set VR rendering to Passed. Mark head tracking and controller input Passed
   only if you actually checked them. Leave stereo depth Not Tested unless it
   has been separately checked.
5. Add notes such as: "Immersion works with VR menu quad, Enable HUD panel and
   World-space interactions/dialogs off, and F10 closed. Stereo depth and extended
   stability not tested." Adjust this to match your actual observations.
6. Save. Expect the latest local test to appear immediately above the bundled
   reference. Copy compatibility report and paste it for review.
7. Open **Test history…**, select the record and try **Copy selected test**.
8. Close/reopen the Hub and verify the record remains.

The Save timestamp is when the report is recorded, not an automatic measurement
of when gameplay occurred. A local timestamp with UTC offset and a UTC timestamp
are stored. Describe an earlier session date in the notes when needed.

History starts empty; bundled recipe references are not silently imported into
local records. You can record the confirmed Skyrim, Fatekeeper and Ready or Not
results yourself. Do not manufacture failed tests or modify a working setup just
to exercise the UI. Cancel leaves history unchanged.

## Result meanings

- Success requires VR rendering Passed and no check explicitly Failed. Other
  checks can remain Not Tested and are displayed that way.
- Partial Success and Failure require notes describing the limitation/failure.
- Rendering, head tracking, controller input and stereo depth each have their own
  Passed / Failed / Not Tested value. Nothing is inferred from the overall result.
- A saved local result does not change automatic configuration readiness, erase
  Cyberpunk's documented workaround, or rewrite the bundled gameplay reference.
- A newer local failure appears prominently above an older successful bundled
  reference. Test history keeps earlier local entries as well.
- A setup snapshot captures the measured configuration findings and documented
  profile workarounds at save time. It is historical, not a verified fingerprint
  of game binaries or actual in-game settings. Dev5 does not automatically decide
  whether an old test is applicable after a configuration change.

Correct a mistaken report by recording a new result with an explanation. Editing
or deleting past entries through the GUI is not part of dev5.

## Local persistence and reports

Records are kept in `~/.local/share/vrhub/live-tests.json`, beside the installer's
state.json. If VRHUB_STATE points elsewhere, history follows that file's parent
directory. Installer bookkeeping, game files, Steam settings and MO2 settings are
not changed by recording a test.

Saves append under a writer lock, use an atomic replacement, and keep the history
file private (0600). Unreadable, malformed or unknown-version history is reported
and is not silently overwritten. Reports remain usable with a visible history
error. No network call or external sharing is performed by saving a local test.

Compatibility JSON retains schema version 1 with additive `local_test`,
`local_test_count` and `local_test_error` fields. Local history JSON has its own
schema version 1. Compatibility text and Copy diagnostics include the latest
local result; Test history includes older entries and their setup snapshots.

## CLI

Record a partial result, using only checks you actually performed:

```fish
python -m vrhub.cli record-test cyberpunk-2077 --result partial --vr-rendering passed --notes "Immersion works with HUD panels disabled; stereo depth not tested."
python -m vrhub.cli test-history cyberpunk-2077
python -m vrhub.cli test-history cyberpunk-2077 --json
```

Optional flags: --head-tracking, --controller-input, --stereo-depth. Each takes
passed, failed or not-tested; the default is not-tested. --result accepts success,
partial or failure. Notes are limited to 4000 characters. record-test also accepts
--json to print the saved entry. A successful save/read exits 0; validation or
persistence errors exit 1. Recording success does not force compatibility exit
status to 0 if configuration checks fail.

## Existing checkout

Choose one patch:

- `dev5-from-dev4-fix2.patch`: incremental from delivered dev4-fix2.
- `dev5.patch`: cumulative from clean v0.4.0 (2e320ac).

From an existing dev4-fix2 checkout on dev/0.5.0:

```fish
git status --short
git apply --check ~/Downloads/NAnnersVRhub-0.5.0-dev5/dev5-from-dev4-fix2.patch
git apply ~/Downloads/NAnnersVRhub-0.5.0-dev5/dev5-from-dev4-fix2.patch
python -m unittest discover -s tests -v
python -m vrhub.gui
```

Preserve unrelated local work. If the check fails, stop and share the error. For
clean v0.4.0 substitute dev5.patch; do not apply both patches. The standalone
source can be tested without editing a repository.

## Validation

146 unit tests pass, covering the existing workflows plus explicit test-result
validation, game-separated append/history ordering, notes/check defaults,
timezone-aware timestamps, setup snapshots, non-mutating reads, private file
permissions, concurrent saves, atomic-write failure, corrupt-history preservation,
CLI JSON/diagnostics and escaped report notes.

Qt smoke checks pass for Cancel, inline validation, modal recording, immediate
report refresh/copy, history selection/copy, subsequent failure, and persistence
after reopening the window. Both the report view and the styled recording dialog
were visually inspected. Both patches reproduce the final source, and tests pass
from the extracted deliverable. Desktop validation remains the next user check.
