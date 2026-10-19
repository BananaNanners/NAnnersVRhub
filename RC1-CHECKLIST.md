# NAnnersVRhub 0.5.0-rc1 desktop acceptance (historical)

October 18 outcome: the user confirmed that all games appeared and saved history
was intact, then replied Pass to the requested gameplay smoke-test list. The
final 0.5.0 notes record that aggregate user report. The checklist below is kept
as the original procedure; its individual boxes/results were not auto-filled.

This is the final candidate checklist. Earlier dev8 export validation is
recorded evidence, not an automatic pass for a new RC1 session. Complete only
the checks actually performed and report any failures with their trigger.

## Extract and launch

```fish
unzip -n ~/Downloads/NAnnersVRhub-0.5.0-rc1-source.zip -d ~/Downloads
and cd ~/Downloads/NAnnersVRhub-0.5.0-rc1
and python -m vrhub.gui
```

Keep using the existing Python/PySide6 installation and working game settings.
The window should show 0.5.0-rc1 and the four existing recipes. State/history
should carry forward from dev8. Keep the extracted source folder available for
resources and any Steam guard path already pointing to a source folder.

## Core desktop pass

- [ ] The window opens as 0.5.0-rc1 with all four games listed.
- [ ] VR System scans without launching a runtime/session or changing settings.
      Headset state follows WiVRn; controller telemetry stays explicitly
      UNVERIFIED. The existing reconnect path still returns to CONNECTED.
- [ ] Readable sampled/test times use the expected 24-hour local zone label.
      JSON scan/collection timestamps retain their native UTC offsets.
- [ ] Existing Fatekeeper/Cyberpunk local history is present after reopening the
      Hub. Earlier records and the latest saved result remain distinct.
- [ ] A support snapshot contains all four sections and visible capture time/age.
      COMPLETE/PARTIAL is collection availability, not a gameplay verdict.
- [ ] JSON + excerpt omission shows OMITTED, a false excerpt option and empty
      excerpt lists; last-occurrence metadata remains. Copy/Save match preview.
- [ ] Text export uses local times and labels historical findings/unknown log
      timezones. Home-prefix replacement works without claiming anonymity.
- [ ] Collect new snapshot updates the collection time; Copy/Save do not
      recollect. Saving under a new filename works and preserves older files.
- [ ] Closing during a scan/collection exits cleanly when the worker finishes.

## Game workflow pass

Use the already installed mods/prefixes/Proton selections. Review the existing
guides and record the result of each game actually tested; historical successes
are not substituted for this session.

| Game | RC1 check | Result / notes |
| --- | --- | --- |
| Skyrim VR / MGO | Correct MO2 shortcut/profile/SKSE entry and prefix; launch, headset view and both controllers | Pending desktop test |
| Fatekeeper | Loaded gameplay -> existing OpenXR injection; 2D Screen Mode off -> close overlay with Insert; headset view, tracking, controls and stereo | Pending desktop test |
| Ready or Not | Existing DX11/VRO setup; mission U entry and Home exit; view/tracking/controllers | Pending desktop test |
| Cyberpunk 2077 | Existing experimental port/panel workaround; view/tracking/controllers/stereo; explicitly note menu passthrough behavior | Pending desktop test |

Cyberpunk's known menu limitation is retained in the candidate notes. A failed
or partial session should be recorded with notes rather than overwriting an
older successful test or changing a bundled reference.

## If a check fails

Preserve the relevant log/config evidence before another launch if it may be
replaced. Collect a new reviewed support report for the selected game and
describe the trigger, expected behavior and actual result. State whether the
problem appeared only with the Hub open or also on an otherwise identical
launch with it closed; do not infer causality from timing alone.

## Existing checkout

Use one included patch:

- `rc1-from-dev8.patch`: incremental from delivered dev8 (427d480).
- `rc1.patch`: cumulative from clean v0.4.0 (2e320ac).

```fish
git status --short
git apply --check ~/Downloads/NAnnersVRhub-0.5.0-rc1/rc1-from-dev8.patch
git apply ~/Downloads/NAnnersVRhub-0.5.0-rc1/rc1-from-dev8.patch
python -m unittest discover -s tests -v
```

Preserve unrelated local work. If the check fails, stop and share the error.
Do not apply both patches. The extracted source can be tested directly.
