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
