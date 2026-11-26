# Dev5G-A6.3-A/B — Synthetic update and conservative compatibility
Baseline ad053670fa6b7040a4748854c6c4d5d7de03da8c.
Player approved conservative policy: never silently delete obsolete managed
files; block unresolved compatibility. Synthetic v1 to v2 transaction changed
one plugin and added one plugin, preserved injector/backend/custom settings/
untracked files and synthetic save; verified ownership, history, no-op and
exact latest-transaction rollback. Real release pins unchanged.
A6.3-A single test passed (0.938s); targeted 89 passed (21.664s).
A6.3-B adds managed dependency/ownership classification, independent refreshed
and staged preflight checks, and existing review dialog blocking including
backend completion callback and direct handler. No new controls.
Tests cover omitted present/missing dependencies, dependency-only/ownership-only
records, malformed ownership, forged review and GUI bypass. First targeted run
117 tests with two GUI subtest errors due to incomplete test inventory; corrected
fixture retained full inventory without weakening validation. Corrected single
GUI test passed (0.024s); 117 targeted tests passed (25.354s), process 11492 exit 0.
Stable state, seven historical manifests and both reboot fixtures verified.
Production gate closed. Synthetic release compatibility only; no live operations.
Full regression, interactive KDE acceptance, update interruption and historical
artifact classification remain pending.
Evidence directories: ~/NAnnersVRhub-recovery/Dev5G-A6.3A-evidence-omVZDP
and ~/NAnnersVRhub-recovery/Dev5G-A6.3B-evidence-xcCduT.

## A6.3-B5 interactive acceptance
Player confirmed all eight KDE desktop checks on November 25, 2026.
Runtime checkpoint 0663c3ececa6178cb9d7328686905a6d06d903b9.
PID 13200, launch 18:46:44 PST; Qt visible 1630x1060, isolated preview
state, stable state checksum unchanged. Process/worktree verified.
No interactive obsolete dependency reproduction or compositor confirmation
claimed; automated disposable compatibility tests passed. Gate closed.
A6.3-A manifest 31ffe82befe57d112cc1b0994462718a1363c508b3a32d70ccaf66a3a0ab838d.
A6.3-B manifest 2bbe9df174b7435e44c2468a64506937be266accc4d72d2898b86a2b0570d751.

## A6.3-C/D update interruption and final validation
Two integrated tests exercise update interruption after payload and state
publication, pending retry refusal, exact v1 restoration, subsequent update,
historical evidence preservation, malformed/changed ZIP rejection and changed
settings rejection. Initial stale-review test expected checksum error for a
malformed ZIP; corrected and added structurally valid modified ZIP case.
Two tests passed (2.860s), targeted 119 passed (27.233s), process 13681 exit 0.
Full regression 1728 passed (67.831s), process 13774 exit 0, no skips/errors/
failures; verified KHARVOX payload included. All nine prior Dev5G manifests
and both A5 reboot fixtures reverified; stable state unchanged; gate closed.
Accepted preview PID 13200 remained running during verification. Tests/docs
only since A6.3-B5; no runtime or real release pin changes. Interruption is
simulated active game, not power failure; synthetic updates not upstream
compatibility proof. A6.3 complete; A6.4 artifact protection pending.
Evidence: ~/NAnnersVRhub-recovery/Dev5G-A6.3C-evidence-aGQlyL.

A6.3-C/D manifest SHA-256: 2ff3ecbc773c31fbf5bfd5bc6d5db22e9e21a4ccf64e14b5b11ef4a9cc636a0c.
