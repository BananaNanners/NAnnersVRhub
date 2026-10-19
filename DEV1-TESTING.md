# NAnnersVRhub 0.5.0-dev1 testing

Based on v0.4.0, commit `2e320ac`. This is a development build for local testing.

## Test separately first

Extract `NAnnersVRhub-0.5.0-dev1-source.zip` into your Downloads folder. In fish:

```fish
cd ~/Downloads/NAnnersVRhub-0.5.0-dev1
python -m unittest discover -s tests -v
python -m vrhub.gui
```

Use your existing system PySide6. If missing on CachyOS/Arch: `sudo pacman -S pyside6`.

1. Open WiVRn and connect your Quest as usual.
2. Open the Hub and select **VR System**.
3. Click **SCAN MY VR SETUP**. Check the selected manifest/library, runtime process, IPC socket, and configured adapter findings.
4. Click **Copy system report** or **Save system report…** to capture the result.
5. Open **Games** and check that all four games still appear. Use the existing game-specific **Preflight**.

Dev1 never claims that a server process or socket proves a connected headset or tracked controllers. Hardware stays **UNVERIFIED** until live telemetry is added. A Vulkan loader finding also does not verify rendering/driver behavior. Detection can miss nonstandard host, sandboxed, or game-local installations.

CLI equivalents:

```fish
python -m vrhub.cli scan
python -m vrhub.cli scan --json
```

Exit code 0 means host prerequisite checks passed; exit code 1 means NOT READY or NEEDS CHECKS. Use `python -m vrhub.cli scan > ~/Downloads/NAnnersVRhub-system-scan.txt` for a shareable report. Review local paths before posting it publicly.

## Apply to your existing development checkout

The archive also includes `dev1.patch`, containing the complete change from v0.4.0. In your existing repository, confirm you are on `dev/0.5.0` and inspect `git status` first. Preserve any unrelated local edits. Then:

```fish
git apply --check ~/Downloads/NAnnersVRhub-0.5.0-dev1/dev1.patch
git apply ~/Downloads/NAnnersVRhub-0.5.0-dev1/dev1.patch
python -m unittest discover -s tests -v
python -m vrhub.gui
```

If the patch check fails, stop and inspect the difference from the v0.4.0 baseline. Do not force it or overwrite local changes. No release tag or main-branch update is needed for this test.

## Validation completed before delivery

- 52 Python unit tests passed, including all previous game/recipe checks.
- Qt offscreen smoke checks passed for dashboard rendering, background scanning, copying/exporting the report, switching tabs, and the four existing game rows.
- `git diff --check` passed.
- Live CachyOS/WiVRn/Quest hardware testing remains on your machine.
