# Dev5G-A2 — Pending production journal transitions
Baseline 43bde6826ece667a79cb49d9df34ec6cd8792992.
Production journal validation rejects the old digest while a new digest is
pending, including missing initial publication. Intended published bytes may
finalize the ledger under lock before further recovery. Unresolved intents
cannot be overwritten by the production writer. Pre-intent staging retries
remain supported. Scoped development behavior unchanged.
Three new tests and revised independent-process initial-intent test passed.
58 targeted tests passed (3.679s); full regression 1691 passed, no skips,
47.095s; process 10393 exit 0. Stable state checksum unchanged; gate closed.
Evidence: ~/NAnnersVRhub-recovery/Dev5G-A2-evidence-p7h4AS.
Trade-off: interruption before journal publication may require manual review.
Same-UID rollback of both evidence stores is outside the guarantee.
No live installations or GUI changes. Remaining atomic publication,
confirmation binding, storage identity and managed repair validation.

Evidence manifest SHA-256: 29d18c3fc15f135255f9d3dba99f02c74420ed98ec299ccf5ea6d685e73d5ec8.
