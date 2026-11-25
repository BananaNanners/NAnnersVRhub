# Dev5E6-E2 — Persistent scoped transaction recovery

Unreleased development; accepted baseline 5348fa173b466607448f93bd6fd1efefd70b346f.
Global production installation/recovery authorization remains closed.

## Implementation
- Separate private authority directory supplied via VRHUB_SCOPED_AUTHORITY_DIR,
  restricted to owned mode-0700 /tmp/nanners-e6-authority-* directories.
- Ledger binds canonical destination and authority identity, with current and
  intended journal digests. Atomic writes and directory sync precede journal
  publication; successful publication finalizes the ledger.
- Fresh process may issue a new explicit single-use recovery permission after
  verifying ledger, journal and incoming state. Old permission cannot transfer.
- Journal and destination guards, existing ordinary fixture recovery, and
  global production gate retained. No GUI source changes.

## Verification
- 74 targeted tests passed, zero failures/errors (7.669 seconds).
- Seven independent-process cases: completed install, exit after first
  dependency write, after applying publication, before committed publication,
  after committed publication, after recovering publication, during rollback.
  Abrupt exits use os._exit(73); payloads synthetic, preflight and game guard
  mocked. Actual scoped commit/recovery and filesystem writes exercised.
- Two additional tests reject invalid JSON and symlinked authority records.
- Expanded full suite: 1634 tests, 1633 passed, one skipped, zero failures/errors,
  40.386 seconds, exit 0. KHARVOX BridgeTests setUpClass requires configured
  verified standalone NANNERS_TEST_BRIDGE_PAYLOAD; not a Fatekeeper failure.
- Stable Hub state SHA-256 unchanged:
  e4000197b5a4cf153e59c18058075d2a9dc312bbe2e3ff7519bae51c99370ef5.
- Evidence: ~/NAnnersVRhub-recovery/Dev5E6-E2-evidence-EvgVyo
  Three verified log copies, 634355 bytes. Manifest SHA-256:
  7f4832e9e12cbf8a4ea8ab90af5ab45603138d28a64bb5a89e05123480ff9631.
  Earlier gameplay evidence and original backups untouched.

## Limits and production blockers
- Authority is separately provisioned by a trusted caller, not a security
  boundary against same-UID code able to modify both stores. A syntactically
  valid substituted ledger from an untrusted authority is not authenticated
  cryptographically; production authority location and provisioning must
  be controlled. Corrupt/missing evidence blocks ordinary recovery.
- /tmp storage survives process restarts, not necessarily reboot. Power-loss
  durability and persistent production storage not validated.
- Crash before first journal publication leaves staging evidence but no
  dependency writes; automatic cleanup/retry not demonstrated. Pending
  transition can accept either recorded digest until reconciliation;
  adversarial stale-ledger replay and all transition/failure windows have
  not been exhaustively tested. Cooperative locking is not a same-UID
  security boundary.
- Historical E1/A/B journals are not retroactively authorized. No actual
  game install or gameplay rerun in E2; E1 gameplay acceptance retained.
- Latest KDE desktop acceptance pending. Production authorization, packaging,
  remaining game testing and release approval remain separate.
