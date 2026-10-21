NAnnersVRhub — VR Mod Hub for Linux

# NAnnersVRhub 0.5.3

A Linux VR mod hub with runtime/headset diagnostics, per-game compatibility,
controller references, install inventories, gameplay-test history and managed
updates. The October 21 rc1 Import/Test/Launch gameplay check passed on the user setup.

## Changes since 0.5.2

- Nine profiles: Skyrim VR/MGO, Fatekeeper, Ready or Not, Cyberpunk 2077,
  Heroic/Epic Hogwarts Legacy, Subnautica, Valheim, experimental Elden Ring,
  and GOG/Heroic DOOM (2016) with KHARVOX.
- Clean controller references with sourced/default/tested evidence labels.
- Subnautica and Valheim install checks and dated user gameplay evidence.
  Elden Ring remains blocked for unsupported executable versions.
- DOOM: install its isolated runner, test the bridge and launch KHARVOX/SFS.
  The standalone bridge is separately versioned and checksum-pinned.
- Thin Hub package: the full bridge source/binaries are installed only on
  explicit DOOM installation. Existing 0.5.2 updater size/resource limits
  are respected. The other profiles start without this optional component.

## Install or update

Linux, Python 3.11+ and working PySide6 are required for the Hub. Close the
old Hub, extract the custom source ZIP and run:

```fish
cd ~/Downloads/NAnnersVRhub-0.5.3
and python3 install.py
and ~/.local/bin/nannersvrhub
```

After the 0.5.3 release is published, existing managed 0.5.2 users can use
Hub updates -> Check now -> Download source ZIP -> Install update -> Restart.
The actual 0.5.2 updater accepted a synthetic stable candidate in container
tests. A real published-endpoint update remains a separate final user check.

## DOOM bridge

The companion is NAnners KHARVOX Bridge 0.2.0 (experimental). Once its release
is published, Install VR runner obtains and verifies its exact custom source
archive, then reuses your verified isolated runner or obtains the exact base.
Before publication, download the companion archive alongside this package
and choose **Import bridge package…** in DOOM. Select
NAnners-KHARVOX-Bridge-0.2.0-source.tar.gz. This verifies and installs the
component, then runs the same runner installer. Existing runner state and
matching probe results are reused; do not remove the working runner to test.

Connect WiVRn -> Test VR bridge -> Launch DOOM VR -> SFS -> campaign gameplay.
KHARVOX and the GOG game remain separate installs. Native Heroic's existing
prefix is reused. Flatpak/custom Heroic roots and Steam DOOM remain outside
the tested route. See UPDATE-TESTING-0.5.3.md for the final published-update check.

## Data and evidence

The installer deploys application files. Game installs, prefixes, saves,
mod inventories, backups and local test history remain in place. The optional
bridge cache and isolated runner are independent of Hub application rollback.
Close the Hub and run `~/.local/bin/nannersvrhub-manage rollback` to switch the
managed application version. It does not uninstall the bridge component.

The October 21 user reports cover standalone DOOM play for 40 minutes,
dev9 rendering/tracking/controller/stereo success, dev10 installation, and
rc1 Import bridge package/Test VR bridge/Launch DOOM VR success. All four
gameplay categories and the sampled local configuration passed in rc1.
Historical logs/configuration snapshots never establish
a current gameplay session. Cyberpunk's reported menu passthrough limitation
and UEVR overlay behavior remain documented in their profiles.

Read RELEASE-NOTES-0.5.3.md and VALIDATION-0.5.3.md for scope and checks.
