# Dev5G-A6.4-A — Read-only recovery artifact inventory
Baseline e0659c91a08b91c57acc9f91e647455f9c9d4af2.
Player approved conservative preservation of unknown/incomplete artifacts,
historical evidence verification, and independent safe active recovery.
A6.4-A introduces an isolated diagnostic module, not wired to authorization.
Directory descriptor traversal with nofollow, private-directory and regular
single-link file checks, bounded enumeration, candidate-only classification.
No content reads, provisioning, adoption, cleanup or authorization.
Initial six tests passed; extended eight tests passed (0.004s), process 14779.
Ten historical manifests and both A5 fixture inventories verified; stable
state unchanged; gate closed. No production operations or GUI changes.
Limitations: names/shapes are not authenticated provenance or byte evidence;
caller hints are not authority. Inventory is not an atomic snapshot and does
not independently validate mount identity. A retained top-level old backup
is currently an orphan candidate until matched to verified history in A6.4-B.
Do not integrate as a maintenance gate until those distinctions are validated.
A6.4-B: verify history journal schemas, identity, exact backup membership,
digests and matching original retained backups without granting historical
rollback authority. A6.4-C: integrate maintenance refusal independently of
safe active recovery. A6.4-D: interruption and full regression.
Evidence: ~/NAnnersVRhub-recovery/Dev5G-A6.4A-evidence-LdtQ6u.

Evidence manifest SHA-256: dbbc1a7ed0f740668a10d4b44adfcf3e97a78ecc70d532311f759c3630133a68.

## A6.4-B — Historical evidence consistency verification
Baseline 8d23e058e2c5bf819a69b1a80510a1db213b87e5.
Read-only verifier reuses strict journal parsing and destination identity;
requires terminal phase, exact historical directory and backup membership,
independently verifies retained copy and original digests, rejects conflicting
journals for one backup, unsafe permissions/links and incomplete history.
Bounded nofollow descriptor reads, 64 MiB per file and 2 GiB aggregate.
Three integrated production-path tests cover corruption, missing/extra members,
invalid schema/identity/phase/path, three history generations, conflicting
journals, unsafe permissions and independent active recovery with corrupted
historical copy plus incomplete history. Fixture inventories preserved.
Initial 9 tests passed (0.826s); extended 11 passed (3.064s); targeted 130
passed (31.033s), process 15268 exit 0, no skips/errors/failures.
Eleven historical manifests and both A5 fixtures reverified; stable state
unchanged, gate closed; accepted preview PID 13200 still running.
No authorization integration, historical rollback authority, live operations
or GUI changes. Consistency is not authenticated historical provenance;
same-UID coordinated modification not protected. Inventory is not atomic;
caller must hold transaction lock and independently validate active provenance
and storage. Full regression and maintenance policy integration pending.
Evidence: ~/NAnnersVRhub-recovery/Dev5G-A6.4B-evidence-fY0pE6.

A6.4-B evidence manifest SHA-256: 5f9407819e2a87e350ffb70f37158f6daf50d2c223a53dabbca7cc8c7dc1306f.
