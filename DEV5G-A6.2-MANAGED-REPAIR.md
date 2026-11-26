# Dev5G-A6.1/A6.2 — Managed maintenance requirements and repair validation
Baseline 2be7c49885c4f5491f4c0d52e6c6ce8f684c781f.
Player approved A6 requirements and latest-transaction rollback rather than
full removal. Keep maintenance player-first: no-op if verified; review and
repair missing/corrupt dependencies; update only approved compatible releases.
Preserve customized settings, untracked additions, saves, unrelated prefix
files, other games' records, unchanged dependencies and previous evidence.
Use existing Install / Update interface; distinguish latest rollback from
full removal. Recovery restores exact pre-transaction state, even if damaged.
Pending transactions require recovery first. No silent adoption/deletion.
Version updates require independent source, hash and compatibility evidence.
A6.2 adds four integrated tests to tests/test_fatekeeper_rehearsal.py:
fresh managed install -> missing backend and damaged plugin -> repair ->
no-op -> rollback; interrupted repair with simulated active game, refusal
of retry, recovery and repeated repair; corrupt previous backup refusal;
stale reviewed plan refusal. Real archive review, preflight, production
transaction and authority paths; synthetic ZIPs/backend, isolated resolvers,
mocked game process and authorization. Disk-backed disposable fixtures only.
Five custom profile files, untracked addition, synthetic save, modes,
ownership, unrelated records, original backup and history verified.
Initial fixture path rejected by FK4 restriction; corrected fixture without
changing restriction. Single test 1 passed (0.960s); targeted 88 passed
(21.532s); full regression 1721 passed (66.508s), process 8062 exit 0;
no skips/errors/failures; verified KHARVOX payload included.
Stable state unchanged, six prior evidence manifests and both A5 fixtures
reverified. No runtime or GUI changes, live operations or reboot. Gate closed.
Evidence: ~/NAnnersVRhub-recovery/Dev5G-A6.2-evidence-9l3jlF.
Limitations: synthetic dependencies; interruption is simulated game activity,
not process crash/power failure. Failed staging can leave incomplete history
artifacts; comprehensive classification deferred to A6.4.
Next A6.3: propose synthetic version-transition tests, exact old/new pins,
compatibility boundaries, obsolete managed-file classification and rollback.
Do not change real approved release pins without separate evidence/approval.

Evidence manifest SHA-256: d9a78981cb7084c5fc2685bd2514957d3e2d194833ae92e1df6c212c6cae1224.
