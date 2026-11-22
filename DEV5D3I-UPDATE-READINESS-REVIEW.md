# Dev5D3-I — Update Readiness & Safe Replacement Planning

## Goal
Provide one read-only per-dependency **Update readiness** assessment inside the existing **Install / Update → Compare versions** disclosure. Reconcile recorded installation provenance, last on-demand file integrity, downloaded archive SHA/release identity, and the separately refreshed online version. Never confuse evidence of a future update candidate with approval to install or replace a mod.

## Facts observed
- Parent is desktop-approved Dev5D3-H1 checkpoint `1ea20e3245d0850fc901c893de7d7a48d8551ef1`. Its worktree was clean when the isolated Dev5D3-I worktree was created.
- Installed source provenance is recorded via `installed_provenance.evidence()`. Some pinned package records identify a release; Cyberpunk's archive filename version remains **filename-only**, and older manual installations may be Unknown.
- On-demand `installed_integrity.verify()` returns per-dependency Verified/Review/Unknown and H1's separate required-mod **presence-only** status. No integrity check is performed merely by opening the comparison.
- Local archive scans include pinned SHA-256 and sometimes uniquely matched official GitHub digest tags, but scan results can be stale, missing, ambiguous or blocked by recipe pins.
- Online results are requested independently through the existing Updates workflow and may be missing or stale; they do not authorize installation or validate compatibility.
- The user prefers a clean five-column GUI, one game at a time, on-demand checks, and the existing KHARVOX and UEVR safety protections.

## Proposed defaults
- Retain the existing five-column comparison table; rename only its fifth header from Comparison to **Update readiness**. Existing comparison reasoning remains visible in the cell tooltip.
- Show read-only, actionable statuses and next steps such as **Scan archives first**, **Archive blocked / ambiguous**, **Installed release unconfirmed**, **Verify installed files first**, **Installed files need review**, **Local archive is older**, **Newer release online** and **Future update candidate · review**.
- Label candidate only when all four sources are independently consistent: identified installed release from Hub-owned cryptographic evidence; complete non-empty SHA-256 file verification for that dependency; required-mod presence ready; verified newer local archive release; and a uniquely matched, comparable last online release. Even then, candidate is **planning only**.
- A recipe pin change or official digest differing from the pin remains **blocked**, regardless of online freshness or installed integrity.
- Do not infer installation from timestamps, file names or equal upstream version labels. Numeric version ordering uses existing conservative comparison; prerelease/non-numeric tags require review.
- The existing selected game, scanner and Updates controls are not duplicated. No new installation, repair, update, automatic backup or download button is added.

## Decision needed
The user explicitly started Dev5D3-I following their accepted read-only milestone proposal. There were no consequential blockers for a conservative implementation. **Manual KDE desktop acceptance is still required**.

## Scope
- New `vrhub/update_readiness.py`: a pure advisory model that combines evidence and always returns `authorized=False`; never reads game files or calls network APIs.
- `vrhub/archive_update_comparison.py`: preserve existing comparison prose and add structured provenance, verified downloaded release, pin-block and online identity metadata for readiness. Where a pinned package has no explicit separate tag, use its current recipe's exact tagged source page after the matching pinned SHA is verified; never derive the tag from arbitrary ZIP names.
- `vrhub/downloads_gui.py`: show a compact readiness summary and the updated fifth column in the collapsed-by-default Compare versions panel. Hover for previous comparison, rationale, next safe step and explicit no-authorization warning. Reevaluate when the user refreshes Updates, rescans archives or completes/cancels a local integrity check. Clear integrity evidence on game switch.
- `tests/test_update_readiness.py`: focused model and GUI safety coverage.
- `tests/manual_launcher_dev5d3i_preview.py`: disposable nine-game KDE harness and synthetic Fatekeeper update-candidate screenshot; the candidate is **NOT** a real game installation finding.

## Safety / rollback
- Source worktree: `~/Projects/NAnnersVRhub-0.5.5-dev5d3i` on branch `dev/0.5.5-update-readiness`. The approved parent H1 worktree and all historical commits remain untouched.
- No real game files, Proton prefixes, Nexus key, mod ZIPs, installed profiles, saved scans, state records, original-file backups, rollback data or compatibility gates were modified.
- Existing live-installer and guided-install gates remain disabled in preview. A future candidate result is informational only and cannot produce a transfer, install ticket, backup token or authorization.
- The read-only model accepts only complete recorded integrity counts and unique supported source matches; stale, inconsistent and unsafe input fails closed. It does not certify runtime compatibility, actual backup recoverability, post-scan file stability or availability of a future replacement mechanism.
- Source rollback: return to parent H1 commit `1ea20e3`. Do not reset or restore user-owned preview state or saved archive histories.

## Tests
- Focused update-readiness, historical comparison, installed-provenance and integrity suites: **64/64 passed** before final extra count test.
- Final full regression: **1,095 tests run, 1,094 passed, 1 skipped**, no failures.
- Final nine-game disposable KDE GUI: **334/334 checks passed**, including unchanged manual archive controls, no legacy drawer, pinned SHA/online evidence, no install bypass, and no cross-game candidate leakage.
- The only interim KDE harness failure was a test string matching "0 future candidates" as a positive candidate; the assertion was corrected to check actual counts and row states. An initial final harness attempt was refused by its intentionally strict disposable-directory prefix gate; rerunning with the approved fixture prefix passed. Neither was a product safety failure.
- Inspected desktop renders of Valheim, Cyberpunk and a **synthetic** Fatekeeper candidate at 1630×1060. The synthetic candidate is labelled test fixture, and does not establish real-world suitability for replacement.
- Development preview state, archive scan history, folder preferences and read-only Nexus credential remained unchanged by the tests.

## Desktop acceptance
1. Compare versions remains collapsed by default; expanding shows the fifth **Update readiness** column without another button or tab.
2. In pinned Valheim/Subnautica packages, missing integrity checks prompt verification rather than claiming updates are ready.
3. Cyberpunk's filename-only Nexus archives, ambiguous candidates and legacy backup protection cannot become safe update candidates.
4. Fatekeeper/Hogwarts Legacy keep unknown/blocked states unless unique official hashes, installed provenance and integrity evidence suffice; mouse-hover shows the explanation and next step.
5. Updates refresh and local scans remain separate; changing games clears previous integrity evidence and any candidate status.
6. No live installation, repair, download, backup replacement or recovery action is triggered by the readiness view.

## Deferred
- Real game update, dependency compatibility solver, verified replacement/rollback preflight, automatic archival/download/update workflow, new install authorizations, advanced candidate simulation across all game types, hardware VR gameplay acceptance and public release.
