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
