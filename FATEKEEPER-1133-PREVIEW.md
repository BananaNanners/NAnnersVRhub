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
