# NAnnersVRhub 0.5.0-dev4-fix2

This update records Ready or Not's successful October 17 live test and Cyberpunk's
successful immersive-rendering workaround from 23:59 on October 17 (Los Angeles).
The test date is local time, even though diagnostic report timestamps use UTC.

## Run

```fish
cd ~/Downloads
unzip NAnnersVRhub-0.5.0-dev4-fix2-source.zip
cd NAnnersVRhub-0.5.0-dev4-fix2
python -m vrhub.gui
```

Select a game -> Compatibility profile -> Refresh compatibility. Ready or Not,
Fatekeeper and Skyrim have USER-REPORTED LIVE TEST references. Cyberpunk shows
USER-REPORTED LIVE TEST — WORKAROUND REQUIRED (experimental).

## Cyberpunk's recorded working conditions

With an actual save loaded:

1. F10 -> General -> VR menu quad: OFF.
2. F10 -> HUD -> Enable HUD panel: OFF.
3. F10 -> HUD -> World-space interactions / dialogs: OFF.
4. Close the F10 settings overlay completely before evaluating immersion.

The user initially saw a floating screen. Disabling the menu quad alone exposed
passthrough, with repeated xrEndFrame res=-39 (XR_ERROR_POSE_INVALID). After the
additional panels were disabled and F10 closed, the user confirmed immersion.

These are the recorded conditions, not changes made by the Hub. The HUD features
listed above are unavailable in this workaround. The mixed-layer submission
hypothesis fits the behavior; the exact underlying fault in the installed build
has not been established. Stereo depth, extended gameplay, restoring the HUD,
and other configurations have not been separately validated.

The reported runner is proton-cachyos-slr, from prefix config_info. No exact
Proton build version was captured, and the Hub does not switch runners.

REVIEW REQUIRED may still appear because current local checks and uninspected
settings are independent of dated gameplay evidence.

## Existing checkout

Choose one patch:

- `dev4-fix2-from-fix1.patch`: from delivered dev4-fix1.
- `dev4-fix2-from-dev4.patch`: from original dev4.
- `dev4-fix2.patch`: from clean v0.4.0 (2e320ac).

For dev4-fix1, from your repository:

```fish
git status --short
git apply --check ~/Downloads/NAnnersVRhub-0.5.0-dev4-fix2/dev4-fix2-from-fix1.patch
git apply ~/Downloads/NAnnersVRhub-0.5.0-dev4-fix2/dev4-fix2-from-fix1.patch
python -m unittest discover -s tests -v
```

Preserve unrelated local work. If the check fails, stop and share the error.
Do not apply several patches. The standalone source needs no repository edits.

Validation: 124 tests pass; GUI evidence/workaround/clipboard checks pass; all
three patches reproduce the final source, and the extracted package passes tests.
