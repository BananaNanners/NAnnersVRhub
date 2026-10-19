# NAnnersVRhub 0.5.0-dev4-fix1

Fatekeeper's October 17 live test succeeded. Its profile now records that result
and shows USER-REPORTED LIVE TEST instead of UNVERIFIED.

The evidence label is stored profile metadata. It does not automatically change
after a game session. REVIEW REQUIRED can still appear for local settings that
are not automatically inspected; it is independent of the dated gameplay result.

## Run

```fish
cd ~/Downloads
unzip NAnnersVRhub-0.5.0-dev4-fix1-source.zip
cd NAnnersVRhub-0.5.0-dev4-fix1
python -m vrhub.gui
```

Select Fatekeeper -> Compatibility profile -> Refresh compatibility. Expect
Gameplay evidence: USER-REPORTED LIVE TEST and an October 17 dated reference.
The runner name is recorded as proton-cachyos-slr; its exact build version was
not captured. Current file checks and manual review retain their existing behavior.

Next live test: Ready or Not -> Compatibility profile -> Refresh compatibility
-> Copy compatibility report. Review that report before changing settings.

## Existing checkout

Use `dev4-fix1-from-dev4.patch` for the original dev4 source, or `dev4-fix1.patch`
for clean v0.4.0 (2e320ac). Choose one patch, preserving unrelated local work:

```fish
git status --short
git apply --check ~/Downloads/NAnnersVRhub-0.5.0-dev4-fix1/dev4-fix1-from-dev4.patch
git apply ~/Downloads/NAnnersVRhub-0.5.0-dev4-fix1/dev4-fix1-from-dev4.patch
python -m unittest discover -s tests -v
```

If the patch check fails, stop and share the error. The full source can be tested
independently. Existing launch/install behavior is unchanged.

Validation: 122 tests pass; GUI evidence/clipboard checks pass; both patches
reproduce final source and the extracted deliverable passes the same tests.
