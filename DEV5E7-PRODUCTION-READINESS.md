# Dev5E7 — Production readiness review (unreleased)

Accepted baseline: b85c53497274bf42b4a979be3010d280dffaf51b.
Development-only implementation and validation; global live gate remains false.

## Verified behavior

- Scoped fresh-install writer durably marks staging before creating backups.
  When no journal has been published and dependency/state destinations remain
  absent, a new explicitly authorized attempt may retain prior staging
  artifacts and create a separate backup. Unexpected entries, symlinks and
  unsafe metadata block retry. No abandoned staging evidence is deleted.
- Fixed private disk-backed scoped namespace:
  ~/.local/share/nannersvrhub-recovery-development, with separate authority
  directory. Persistent scope ignores the temporary authority override.
  Tests provision a disposable fake HOME on the actual home filesystem.
- Duplicate JSON authority keys are refused. Replaying exact committed journal
  bytes after a completed rollback is rejected with the current ledger intact.
- 82 targeted tests passed (12.038 s); eight new cases cover backup and initial
  intent interruptions, unexpected files and symlinks, disk-backed recovery
  and retry, genuine stale journal replay, duplicate authority fields.
- Full suite: 1642 tests reported, 1641 passed, one skipped, no failures/errors
  (46.845 s, exit 0). KHARVOX BridgeTests setUpClass skip requires verified
  standalone NANNERS_TEST_BRIDGE_PAYLOAD. Scoped subprocesses use synthetic
  dependency bytes and mocked preflight/game guard, not live gameplay.
- Production gate independently checked before and after full testing.
- Stable Hub state SHA-256 unchanged:
  e4000197b5a4cf153e59c18058075d2a9dc312bbe2e3ff7519bae51c99370ef5.
- Evidence: ~/NAnnersVRhub-recovery/Dev5E7-evidence-V0Cmlz
  Two byte-for-byte verified log copies (326096 bytes).
  Manifest SHA-256:
  d3f88b3b0afc084629200d8f7a5b1a3d959afa03feb5096360a2340662864c86.
- No GUI source changes, live game writes, or publication.

## Production activation decision: NOT READY TO ENABLE

1. The new authority and staging path is scoped to disposable fresh installs.
   Ordinary live install/recover still do not invoke it. Do not enable the
   global gate as a substitute for production authority integration. The
   production resolver, state ownership, existing-install/update handling and
   explicit approved operation must use the same safety guarantees.
2. Disk-backed process restarts passed; real reboot and power-loss behavior
   were not tested. Device/inode identity stability across remounts and
   controlled production directory provisioning require verification.
3. Ledger integrity is a cooperative application trust boundary, not
   authentication against arbitrary same-UID modifications. Exact stale
   journal replay with intact finalized ledger passed. Simultaneous rollback
   of both stores and replay within a pending two-digest transition are not
   prevented by this test. Missing journal after initial intent is treated
   as pre-publication only if fresh destinations and permitted staging
   entries remain; arbitrary evidence deletion is outside the guarantee.
4. Staging retry validates allowed artifact names/type/ownership/mode, not
   original bytes of every abandoned staging file. Evidence is retained,
   never trusted as incoming payload. Abrupt termination during atomic
   temporary-file creation/publication has not been exhaustively exercised;
   unknown temporary entries may fail closed and need manual review.
5. The ledger schema gained a required staging field; older scoped ledgers
   lacking it are refused, not migrated or retroactively authorized.
6. Persistent development parent is fixed relative to HOME, not a fully
   provisioned production trust store. Root/authority path checks do not
   establish a general guarantee against ancestor bind mounts or same-UID
   path substitution. Production destination and storage checks need review.
7. Final KDE desktop acceptance passed (8/8). No new game or headset test in E7;
   E6 accepted actual gameplay evidence remains historical and unchanged.

Nearest player outcome: verified dependencies install via the existing
Install / Update workflow without requiring manual DLL placement. Integrate
the scoped protections into a gated production path and demonstrate the same
workflow in disposable conditions before requesting explicit live approval.
Do not add new tabs, selectors, or speculative infrastructure.

## Interactive KDE acceptance — November 25, 2026

Player confirmed all eight desktop checks passed: preview, navigation,
Install / Update organization, archive scanning/dependency recognition,
verified backend status, VR System/runtime detection, no extra controls,
and closed installation/recovery gates. Previous PID 80991 closed normally;
new preview PID 85441 launched from runtime checkpoint
f20299c78f96a0fd9b33641626a03ccf293f00a3. Stable Hub state hash unchanged.
Development acceptance complete; production activation remains blocked
pending integration and the limitations above.
