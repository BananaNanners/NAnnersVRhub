# Fatekeeper Nightly 1133 preview acceptance

Parent checkpoint e71ba12. The Y4 idle-state branch is separate.

| Checklist | Result |
| --- | --- |
| Baseline and clean worktree before development | PASS |
| Nightly 1133, regular joeyhodge backend, profile v1.0.4 identities and SHA-256 | PASS |
| Two-archive scan and read-only review | PASS for automated checks, KDE acceptance pending |
| Verified replacement and preservation of matching backend | PASS in disposable transaction rehearsal |
| Fresh install, legacy repair, full profile payload, custom file preservation | PASS in disposable transaction rehearsal |
| Interrupted commit recovery and rollback of files and fixture ownership inventory | PASS in disposable transaction rehearsal |
| Existing Hub installation and profile recovery regression tests | PASS in the complete automated suite |
| Interactive KDE acceptance | PENDING |
| Production transaction wiring, real Hub record transaction and live installation | PENDING |
| Live Quest 3 gameplay, LuaLoader, head tracking and stereo depth | PENDING |

Tested the real pinned release bytes and used synthetic prior installs. The
preview mounts no live destination for writing. The rehearsal backs up and
restores its own ownership inventory. It has no authority to update the live
Hub state or the Fatekeeper prefix.

Nightly debug symbols are excluded from staging. The code stages all files in
the reviewed profile, including plugin DLLs. Historical update/scan cases retain
an explicit legacy test fixture, and existing user records are never migrated by
this milestone.

## Hub state rollback verification

Checkpoint 7c2db61 restores exact disposable Hub state bytes, including legacy recovery records, after an interrupted Fatekeeper repair. Real pinned payload verification passed. Focused suite: 14 passed. Full suite: 1,498 passed, 1 skipped. Production installation is still gated. The accepted e536c29 KDE preview remains open.

## Installer preflight

The reviewed source stages the same pinned two-ZIP payload used by the
rehearsal. Preflight binds it to the Hub-resolved prefix and reviewed injector
and profile snapshots, skips files whose digests match, and returns a proposed
write set. Existing destination files and Hub records are read-only.

PASS: real pinned asset preflight against disposable destinations, 15 focused
tests, and 1,499 full-suite tests passed (one skipped). The player-accepted
e536c29 KDE preview remains open. No UI changes in this checkpoint.

PENDING: connect this plan to a durable production commit and recovery journal,
then review that workflow in KDE before any authorized live test.

## Dev5D3-FK5 - Live Installer Gate & Acceptance

The player accepted FK4 2d3c88e8f83decf55e5b4b51fbf5c6b50da54828 on KDE.
FK5 connects the pinned review to the Hub's install and recovery paths.
The separate live gate denies execution before resolving any live target.

PASS: real pinned assets in disposable fresh and repair installs, rollback
of files and exact prior Hub state, and gated entry point tests. The focused
suite passed 22 tests. The complete suite passed 1,506 with one skipped.

PENDING: FK5 KDE acceptance and separate live authorization. Recover any
active or committed transaction before opening another journal. Prior
recovery artifacts are retained on retry.

## Dev5D3-FK6A - Smart File Preservation

Read-only FK6 review identified local SDK discovery metadata and a Warden's
Ring attachment configuration as unnecessary replacements. FK6A preserves
those files and the profile config.txt when present, still fills missing
files, and repairs changed packaged components such as the backend. The
existing review shows Install, Replace, and Preserve decisions. An empty
write set skips the transaction and Hub record update.

Disposable fresh install, repair, interruption, and rollback passed.
Focused suite: 23 passed. Full suite: 1,507 passed, one skipped.
The working Fatekeeper prefix has zero proposed writes and 115 preserved
files. KDE acceptance pending. The live gate remains closed.

## Dev5D3-FK6B - Gameplay Validation on the Existing Install

2026-11-23 (Pacific): Player accepted the FK6A KDE preview at 0280b36,
explicitly confirming preservation of SDK discovery metadata and the attachment
configuration. FK6B read-only preflight rechecked the pinned archives and
existing backend: Install 0 / Replace 0 / Preserve 115. The live-write gate
was closed. No installation, repair, rollback, or Hub state write was run.

Gameplay acceptance is pending for this run: LuaLoader, VR rendering, head
tracking, stereo depth, and left and right Quest 3 input. Controller results
are player-reported. Previous successful sessions are historical evidence.

## Dev5D3-FK6B1 - Full Hub Preview Fidelity

Player outcome: launch Fatekeeper or Hogwarts from the same Hub controls
used for gameplay, and understand why an archive is blocked before changing
any game files. The full KDE preview reuses private preview state while
reading host Heroic metadata and passing host XDG paths to launch children.

Verified discovery of both games, Hogwarts's existing Proton-CachyOS-latest
runner and prefix, and launch-button dispatch with process starts mocked.
A Fatekeeper checksum failure opens the existing blocked review with archive,
pinned version and approved source. Focused: 52 passed. Full: 1,509 passed,
one skipped. KDE player acceptance and actual launches are pending. Live mod
installation, removal and recovery remain gated.

Next: FK6B live gameplay validation on the unchanged Fatekeeper install,
then FK7 sign-off and E1 controlled real-world update pilot.

### FK6B1 corrective patch

Steam UEVR launches now wait for their direct Protontricks child and block a
duplicate launch for that game while it is pending. Protontricks 1.14.1 waits
synchronously on its Wine command; the observed start.exe ntsync wait is
consistent with the lingering launcher, but the precise Wine hang and the
separate OpenXR -51 error remain open. No process tree is terminated.

The preview reads the host OpenXR selection on every probe and honors explicit
runtime overrides. The host probe reported WiVRn selected, running, and a Quest 3
connected through WiVRn telemetry. A checksum failure uses the normal UEVR review
and blocks installation; the failed ZIP is not parsed.

Focused: 54 passed. Full: 1,511 passed, one skipped. KDE acceptance pending.
Return directly to FK6B gameplay and -51 investigation after acceptance.

### FK6B corrective acceptance and OpenXR diagnosis

Player accepted the FK6B1 corrective KDE preview at
19f4d79c08de2cc5a20de7e6874c480514be47d7. The approved code is unchanged.

Read-only evidence: WiVRn host selection resolves to openxr_wivrn.json.
The prefix registry routes through wineopenxr64.json and its wineopenxr.dll
exists. The installed UEVR openxr_loader.dll matches the pinned Nightly ZIP.
UEVR log.txt records OpenXR instance failure -51 at 21:15:23 Pacific on
2026-11-23 and Lua state initialization immediately afterward. Steam tracked
the game. Stored launch options include the OpenXR runtime import flag, but
the failed game and injector environments were not captured. Proton log
unavailable at the standard home location. The October success establishes
historical gameplay with the Steam/Proton workflow, not exact launch parity.

The supervisor reaps exiting direct children. Its duplicate guard can
block relaunch while a Wine helper keeps an old launcher alive. No process
or configuration was changed in this diagnosis.

Next test is player-initiated with existing settings. Sample the actual
game and injector process environment allowlist, loader mappings and fresh
logs, then observe cleanup on normal exit. Current headset gameplay,
input and exact cause of -51 remain pending.
