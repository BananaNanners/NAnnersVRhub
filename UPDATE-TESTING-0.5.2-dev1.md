# 0.5.2-dev1 — automatic Hub downloads and in-app updates

Development preview; not published to GitHub. Built from accepted 0.5.1.

## Desktop acceptance

1. Close the old Hub, extract this ZIP and run `python install.py` using the same
   Python/PySide6 installation as 0.5.1. Open the application-menu entry or
   `~/.local/bin/nannersvrhub`; the title should show **0.5.2-dev1**. Confirm all
   four games and your saved test history are present.
2. Open **Hub updates…** above the main tabs, then **Check now**. The official
   latest stable is currently **0.5.1**, so this development build should report
   that it is newer. This is expected; **Install update…** must remain disabled.
3. Choose **Download source ZIP**. The download should finish as verified, show
   its release notes, and enable **Open verified download**. Close/reopen the Hub
   and the update screen; the cached check/download should recover. This step
   tests actual desktop HTTPS and the published checksum without downgrading.
4. Enable automatic downloads if desired. It downloads only a **newer stable**
   release after a check. Close/reopen and confirm the preference persists. Leave
   startup checking enabled for daily checks, or turn it off and use Check now.
5. With the network disconnected, Check now should show a connection error while
   the Hub and game list remain usable. Automatic failures wait 24 hours before
   another startup attempt; manual checks can retry immediately. Cancel a slow
   download/check if convenient; installation must remain unchanged.
6. Confirm your games still launch as expected. No fresh gameplay results are
   recorded automatically.

A complete real-public-release upgrade check becomes possible after publishing a
stable release newer than this preview. Then check, download, choose **Install
update…**, review its confirmation, and choose **Restart Hub**. The installed
version should change while saved data stays intact. Rollback remains
`~/.local/bin/nannersvrhub-manage rollback`; repeating it returns to the update.
The isolated automated test exercises this sequence with a synthetic 0.5.3
fixture; that fixture is not an available release or gameplay test.

## Behavior and failure handling

- Stable official releases only; prereleases, arbitrary repositories, generated
  GitHub source archives, downgrades and malformed/missing release assets are
  rejected. Exact assets: `NAnnersVRhub-VERSION-source.zip` and `SHA256SUMS`.
- Uses public unauthenticated GitHub HTTPS; no Nexus key, GitHub login, dependency
  download, elevated permission or background service. Requests use 8-second
  socket timeouts and bounded reads. Manual checks may encounter GitHub rate
  limiting; the error leaves the installed application usable.
- Source ZIP limit 32 MiB; expanded limit 128 MiB, 2,000 entries and 8 MiB per
  member. Unsafe/duplicate paths, links, special files, encrypted entries,
  incomplete downloads and mismatched versions/checksums are rejected. Partial
  failed downloads are removed. Valid cached content is rechecked before install.
- Checksums downloaded through the same official GitHub release provide integrity
  checks, not independent publisher signatures. This flow trusts that official
  repository and HTTPS. It does not claim independent code auditing.
- Installation is enabled only from the active managed release. The installer
  performs its existing dependency probes and atomic activation, preserving a
  previous version. A stale running window cannot overwrite another activation.
  The old process keeps using its original modules until restarted.
- Closing the update dialog keeps its worker running. Closing the Hub cancels a
  network operation and waits for it to finish; an installation finishes its
  atomic operation before closing. Cancelling installation midway is disabled.
- No game/mod/runtime settings, Steam options, compatibility verdicts or local
  gameplay records are updated by the application updater.

## Storage and recovery

Preferences/check metadata: `hub-updates.json` beside the existing Hub state file
(`~/.local/share/vrhub/` by default, respecting `VRHUB_STATE`). Its lock and atomic
writes are separate from state/history. Malformed preferences are preserved and
reported instead of overwritten.

Downloads: `$XDG_CACHE_HOME/nannersvrhub/updates/` or
`~/.cache/nannersvrhub/updates/`, in private per-download folders. Each folder
contains the source ZIP, SHA256SUMS, extracted source and verification record.
**Open verified download** opens that folder; the original ZIP is retained.
Cache folders can be removed while the updater is idle; an invalid/missing cached
download prompts a new download. Corrupt application installation records remain
the installer's responsibility; the updater does not repair them silently.

Installed application copies/launchers remain in the existing 0.5.1 layout; see
[INSTALL-0.5.1.md](INSTALL-0.5.1.md). Python/PySide6 upgrades remain manual.

## Developer validation

```sh
python -m unittest discover -s tests -q
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -q
```

The second command needs PySide6 and includes a real isolated Qt worker flow,
managed activation, stable-launcher version checks and two-way rollback. Fixtures
use separate home/state/cache directories and do not access real games.
Network tests use deterministic release/HTTP fixtures. The published 0.5.1 asset
and retrieved GitHub metadata are also replayed against the download verifier;
desktop live-network acceptance remains step 3 above.

Build validation: **263 tests passed with PySide6**, including six Qt updater
checks. Wheel and sdist resources/entry points, a wheel launched outside the
checkout, a missing-Qt installation check, and sdist rebuild/tests also passed.
The published archive replay verified both GitHub asset digests and SHA256SUMS,
cached recovery and rejection of a downgrade.

References: [GitHub releases API](https://docs.github.com/en/rest/releases/releases)
and [release asset API](https://docs.github.com/en/rest/releases/assets).
