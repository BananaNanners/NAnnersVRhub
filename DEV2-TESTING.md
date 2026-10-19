# NAnnersVRhub 0.5.0-dev2 testing

Dev2 builds on the dev1 dashboard you tested successfully with CachyOS, WiVRn and Skyrim VR/MGO. It adds live WiVRn connection status and fixes custom adapter inventory reporting. Game launch configuration remains unchanged.

## Run the complete source package

Extract the ZIP in Downloads, then in fish:

```fish
cd ~/Downloads/NAnnersVRhub-0.5.0-dev2
python -m unittest discover -s tests -v
python -m vrhub.gui
```

Use the existing system PySide6. On CachyOS/Arch, `busctl` is supplied with systemd. There is no new Python runtime dependency.

## Live connection validation

Keep the Hub on **VR System** and leave **Auto-refresh live status every 5 seconds** enabled.

1. Open WiVRn and connect your Quest normally. Expect **Runtime: WiVRn SELECTED**, **Server: RUNNING**, and **Headset: CONNECTED**. If WiVRn provides it, the report includes the headset system name.
2. Confirm **xrizer host inventory** reports `/opt/xrizer` as found. It should agree with the configured adapter row.
3. Disconnect the headset using your normal WiVRn workflow while leaving the server running. Expect **Headset: DISCONNECTED** within the next completed poll if WiVRn keeps its status service available.
4. If stopping/disconnecting also removes WiVRn's D-Bus service or switches the selected runtime, expect **UNKNOWN** instead. A missing service cannot prove a disconnected state.
5. Reconnect normally and confirm **CONNECTED** returns.
6. Click **Copy system report** and paste the connected report for review. Copy the disconnected/unknown report too if a transition looks wrong.

Controller status stays **UNVERIFIED** because these properties do not include live controller tracking. Your earlier successful gameplay check remains separate evidence.

If status stays UNKNOWN while the headset is connected, the report gives the reason. For a direct read-only diagnostic (no startup, pairing, or configuration changes):

```fish
busctl --user --auto-start=no --allow-interactive-authorization=no --timeout=1 --no-pager call io.github.wivrn.Server /io/github/wivrn/Server org.freedesktop.DBus.Properties Get ss io.github.wivrn.Server HeadsetConnected
```

Expected connected reply: `v b true`; disconnected reply: `v b false`. Missing/unsupported/inaccessible service replies remain UNKNOWN. This diagnostic reads the existing user session bus only.

CLI:

```fish
python -m vrhub.cli scan
python -m vrhub.cli scan --json
```

The CLI takes one sample; the GUI performs the automatic refresh. Exit 0 still means host checks passed, regardless of connected/disconnected/unknown hardware status.

## Apply to your existing development checkout

The ZIP includes two patches. Choose the one matching your checkout; do not apply both:

- `dev2-from-dev1.patch`: incremental update when the dev1 source changes are already in your checkout.
- `dev2.patch`: cumulative update from the clean v0.4.0 baseline (`2e320ac`).

In your existing repository, confirm `git branch --show-current` is `dev/0.5.0` and inspect `git status`. Preserve unrelated local changes, then for an existing dev1 checkout:

```fish
git apply --check ~/Downloads/NAnnersVRhub-0.5.0-dev2/dev2-from-dev1.patch
git apply ~/Downloads/NAnnersVRhub-0.5.0-dev2/dev2-from-dev1.patch
python -m unittest discover -s tests -v
python -m vrhub.gui
```

For a clean v0.4.0 checkout, substitute `dev2.patch`. Stop if the patch check fails; do not force it or overwrite local changes. No main-branch update or release tag is needed for this test.

## Validation before delivery

67 unit tests pass, including all previous game/recipe checks, typed/malformed status replies, timeouts, unavailable service, no-start command construction, optional metadata, runtime switching, adapter inventory, and stale connection clearing. Qt offscreen smoke checks cover automatic connected → disconnected → unknown transitions, copy/save, tab switching, worker cleanup and close during a query. Tests use telemetry fixtures; live WiVRn hardware/D-Bus validation remains on your system.
