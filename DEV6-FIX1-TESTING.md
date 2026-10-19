# NAnnersVRhub 0.5.0-dev6-fix1 testing

Fix1 corrects a log-recognition defect. It does not fix the game's frame submission
or automatically change UEVR configuration. The rendering regression remains
under investigation.

## Run

Extract the new ZIP, then run in fish:

```fish
cd ~/Downloads/NAnnersVRhub-0.5.0-dev6-fix1
python -m unittest discover -s tests -v
python -m vrhub.gui
```

Open Fatekeeper -> Compatibility profile -> Log diagnostics. The same failing log
should now show recognized validation failures and informational frame discards.
Counts cover only the inspected tail, so they will be smaller than a whole-log
count. Refreshing a live log may also change the counts.

## What the supplied evidence establishes

The October 18 log records the OpenXR system as Meta Quest 3 on WiVRn and reaches
a focused session. Across the complete uploaded log, there are 13,984
`xrEndFrame ... XR_ERROR_VALIDATION_FAILURE` messages and 13,983
`xrBeginFrame ... XR_FRAME_DISCARDED` messages. Both also occur in the bounded tail
that dev6 inspected. Its initial signature set missed them; tail truncation alone
does not explain the missed diagnosis.

The current config records `VR_2DScreenMode=true`. That is a testable setting,
not proof of the cause of the validation failures or proof of who changed it.
The Hub's Fatekeeper launch/install/profile functions and relevant recipe
settings are unchanged from the delivered dev2 baseline. This audit does not
rule out every interaction while the Hub is running.

## One-setting gameplay test

With Fatekeeper loaded into gameplay and OpenXR injection active, open UEVR with
Insert. Turn **2D Screen Mode** off, then close Insert completely and observe the
headset. Keep the existing synchronization, Proton, runtime, mod and profile
settings in place so the result can be attributed to this one setting change.
The toggle is reversible; the uploaded config preserves its previous true value.

If passthrough remains, preserve the new log before another launch. The next
investigation needs runtime-side validation details identifying the rejected
parameter, and a controlled launch with the Hub closed. Fix1 does not declare an
exact mixed-layer, timing, controller or injection cause from these messages.

## Error/status semantics

- `XR_ERROR_VALIDATION_FAILURE` is recognized as an error by exact symbol or a
  failed OpenXR call with `res=-1` / `result=-1`. It can apply to calls other than
  xrEndFrame, so the explanation retains that distinction.
- `xrBeginFrame ... XR_FRAME_DISCARDED` is recognized as informational. OpenXR
  defines +9 as a success status indicating a prior begun frame was discarded.
  The word "failed" or error level in a plugin log does not change the API's
  classification. When it alternates with rejected xrEndFrame submissions, those
  validation failures deserve investigation first.

Primary references:
[XrResult](https://registry.khronos.org/OpenXR/specs/1.1/man/html/XrResult.html),
[xrEndFrame](https://registry.khronos.org/OpenXR/specs/1.1/man/html/xrEndFrame.html),
[xrBeginFrame](https://registry.khronos.org/OpenXR/specs/1.1/man/html/xrBeginFrame.html),
and UEVR's **2D Screen Mode** label / stored toggle in
[VR.cpp](https://github.com/praydog/UEVR/blob/master/src/mods/VR.cpp) and
[VR.hpp](https://github.com/praydog/UEVR/blob/master/src/mods/VR.hpp).

## Existing checkout

Choose one patch:

- `dev6-fix1-from-dev6.patch`: incremental from delivered dev6 (e54f8b8).
- `dev6-fix1.patch`: cumulative from clean v0.4.0 (2e320ac).

Check before applying. Do not apply both; preserve unrelated local edits.

```fish
git apply --check ~/Downloads/NAnnersVRhub-0.5.0-dev6-fix1/dev6-fix1-from-dev6.patch
git apply ~/Downloads/NAnnersVRhub-0.5.0-dev6-fix1/dev6-fix1-from-dev6.patch
```

## Validation

170 unit tests pass, including four new tests for the actual missed pattern,
symbolic/positive-status distinctions, numeric false positives and unchanged
config/history. The complete supplied log is used locally to check the fix;
the release contains only a minimal anonymized synthetic reproduction.
