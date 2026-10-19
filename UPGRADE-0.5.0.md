# Upgrade to NAnnersVRhub 0.5.0

The final release promotes the accepted RC1 build. Runtime behavior, the four
recipes, state/history storage and report schemas remain unchanged from RC1.

## Run the final source archive

In fish after downloading:

```fish
unzip -n ~/Downloads/NAnnersVRhub-0.5.0-source.zip -d ~/Downloads
and cd ~/Downloads/NAnnersVRhub-0.5.0
and python -m vrhub.gui
```

The window should show 0.5.0 and existing saved gameplay history. Use the current
Python 3.11+ and PySide6 installation. No history migration, mod reinstallation
or Proton/runtime change is required to run the new Hub source.

State remains in `~/.local/share/vrhub/state.json`; local tests remain beside it
in `live-tests.json`. With VRHUB_STATE, history follows that file's parent.

Keep the source folder in a stable location. Existing Steam launch options may
refer to an older folder's `vrhub-check` script; extracting the final archive
does not rewrite those options. Keep that referenced folder available until you
have explicitly reviewed/replaced the corresponding guard path. The supported
distribution is extracted source or an editable checkout, not a standalone
non-editable wheel/system package.

## Existing git checkout

Use exactly one included patch:

- `v0.5.0-from-rc1.patch`: incremental from delivered 0.5.0-rc1.
- `v0.5.0.patch`: cumulative from clean v0.4.0 (2e320ac).

From a matching checkout:

```fish
git status --short
git apply --check ~/Downloads/NAnnersVRhub-0.5.0/v0.5.0-from-rc1.patch
git apply ~/Downloads/NAnnersVRhub-0.5.0/v0.5.0-from-rc1.patch
python -m unittest discover -s tests -v
python -m vrhub.gui
```

Preserve unrelated work. If the check fails, stop and share the error. Do not
apply both patches. A source ZIP can be run directly without patching a checkout.

## Evidence and continuing support

The final version preserves known Fatekeeper/Cyberpunk menu workarounds and
historical log findings. A new gameplay result should be recorded explicitly
with checks actually performed. Collect a fresh reviewed support report for a
later issue; Copy/Save alone retain the already captured snapshot.
