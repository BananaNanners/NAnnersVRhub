# Dev5G-A4 — Exact recovery confirmation
Baseline 7521de6dcee8485a7ac86d827db904d0ea8c382a.
Production recovery requires an exact immutable review of the trusted journal,
destination, authority identity, phase, backup and affected dependency count.
The review is revalidated under the transaction lock before ledger finalization
or recovery. Existing engine validates backup and destination bytes. Existing
GUI dialog captures the review before confirmation; decline does not execute.
CLI review-recovery fatekeeper prints the exact fingerprint; uninstall-profile
fatekeeper requires both --yes and --approve-recovery matching that fingerprint.
Direct paired uninstall passes the explicit review to the same gated engine.
Six new disposable tests cover missing approval, changed trusted transaction,
destination mismatch, CLI fingerprint, GUI capture and cancellation.
Initial targeted 132 passed (16.629s); final targeted 134 passed (17.151s).
Full regression 1704 passed, no skips/errors/failures (48.539s), process
14001 exit 0; verified KHARVOX payload included.
Stable state SHA-256 unchanged; A1-A3 evidence reverified. Global gate closed.
No live recovery or installation. No new GUI controls. Approval binds transaction
identity, not an authenticated same-UID security boundary. Backup integrity
continues to be independently checked by the engine. CLI fingerprint is not
a secret token. Interactive KDE acceptance passed (8/8).
Evidence: ~/NAnnersVRhub-recovery/Dev5G-A4-evidence-jW9JcY.
Next: A5 storage identity and reboot verification; no reboot without separate
player approval. Remaining managed update/repair and production readiness review.

Evidence manifest SHA-256: d1bc6fef676c93548cf19966d06df9d5ff473efc482c701d352b1861b4016914.

Player confirmed all eight KDE checks on November 25, 2026. Runtime checkpoint ad1180c8c8dbfea7479402151a301bf3bd8861dd, PID 14832, launch 17:36:56 PST. KWin verified one non-modal visible preview at 17:37:10 PST, 1630 x 1088. Previous preview absent. Stable state checksum matched before and after launch. Live dialog remains gated; acceptance is not production recovery authorization.
