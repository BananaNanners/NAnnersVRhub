# Runner installer check — 0.5.3-dev10

Install this preview using its own `python3 install.py`, then restart the Hub.
Do not use an older in-app updater to install the bridge package.

1. Confirm all nine games and existing local test histories still appear.
2. Close DOOM/KHARVOX and select DOOM -> Install VR runner.
3. On the existing tested setup, expect "Existing isolated runner verified and reused".
   No download or second full runner copy should be needed.
4. Connect WiVRn -> Test VR bridge -> Launch DOOM VR -> SFS -> Launch Game.
   Check rendering, tracking, both controllers and stereo depth in a campaign.
5. Open DOOM diagnostics if an action fails; preserve the complete installer
   output from its action window as well as any probe/game logs.

The installer also supports a fresh machine without the pinned Heroic runner.
It obtains the 319.5 MiB upstream archive, verifies size/SHA-256 and all seven
baseline files, then prepares an isolated copy. This path was exercised in
an empty container state with the actual upstream archive, without Wine or a
headset. The same downloader fetched and verified the actual release. This
is installation evidence, not a second user's live gameplay result.

Do not delete your working runner just to simulate a new machine. The
standalone bridge can use `--state /an/empty/separate/directory` for an
optional separate install test (about 4 GiB free space required).

To remove an installer-owned isolated runner, close DOOM/KHARVOX and run from
this Hub source directory:

```fish
python3 vrhub/bridge_installer.py uninstall --payload vrhub/assets/kharvox-lab-0.1.6 --confirm-remove-runner
```

This preserves game files, saves, Heroic settings, diagnostic logs and cached
downloads. It removes the runner and its pass metadata; another install/test
will be required before launching DOOM VR. Avoid uninstalling the known
working runner unless you intend to remove it.

This development build does not publish a repository, tag or release. The
standalone source project is prepared separately for review.
