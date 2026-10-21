# Subnautica — dated user success and stock controls

0.5.3-dev2 updates the bundled evidence and guide. The Subnautica installer,
mod versions and launch-option text are unchanged from dev1. Existing local
FAILURE/SUCCESS reports, mod inventories, backups and saves are not rewritten.
There is no need to reinstall the game mods for this Hub update.

## Recorded evidence

The user recorded SUCCESS on October 19, 2026 at 23:00:22 PDT in 0.5.3-dev1:
VR rendering, head tracking, controller input and stereo depth all PASSED.
A and trigger interaction worked flawlessly in that test. The compatibility
snapshot remained REVIEW REQUIRED because manual configuration checks were
not automatically inspected. A dated gameplay success is separate from the
current configuration scan or another session's behavior.

Setup: CachyOS, Quest 3, WiVRn active, host xrizer configured at /opt/xrizer.
The prefix recorded proton-cachyos-slr, but the exact Proton build and running
Steam selection were not verified. The installation inventory found all 45
recorded files from SubmersedVR 0.2.1 and Tobey's BepInEx pack
5.4.23-pack.3.1.1. Loaded DLL paths were not captured.

Use Steam's **Launch Subnautica in Steam VR Mode** choice. The earlier regular
Play Subnautica test stayed flat; its log showed SubmersedVR loaded, followed
by OpenVR initialization failure and camera-rig exceptions. Connect WiVRn first,
keep host xrizer selected and retain the copied Steam launch options.

## Preferred stock controls

- **Y:** open/close the PDA.
- **Hold A and drag an item into a quick slot:** the user-confirmed assignment method.
- **A and trigger interaction:** worked in the October 19 live test.

Avoid the in-game binding editor. The user reported it gets stuck waiting for
a button and cannot cancel. An external Menu-button PDA layout worked but
felt uncomfortable, so the user preferred stock bindings and requested its
reversal. Y -> UIAssign did not work in that external test. It is not recorded
as a successful quick-slot method.

The Hub does not install any custom binding override. The separate experiment
used Subnautica/xrizer/oculustouch.json; reverting it means disabling that file
and returning to the mod's shipped bindings. Merely upgrading the Hub does
not change any manually created override. The author archives and pinned hashes
are unchanged. Longer sessions, other headsets/setups and every game feature
remain outside this user-reported reference.

## Upgrade from dev1

Close the Hub. Save the ZIP in Downloads and run in fish:

```fish
unzip -n ~/Downloads/NAnnersVRhub-0.5.3-dev2-source.zip -d ~/Downloads
and cd ~/Downloads/NAnnersVRhub-0.5.3-dev2
and python install.py
and ~/.local/bin/nannersvrhub
```

Check that all six games and your local test history remain visible. Subnautica's
bundled reference should now say USER-REPORTED LIVE TEST with the October 19 date.
Your existing test records keep their original notes and configuration snapshots.
Manual settings warnings can still leave the current scan at REVIEW REQUIRED.
The stable in-app channel remains 0.5.2; this development ZIP is installed manually.

For a new mod installation, follow the recipe's pinned author download links and
select both ZIPs together. The original [dev1 installation guide](SUBNAUTICA-TESTING-0.5.3-dev1.md)
remains historical; use this document for current test evidence and control advice.
