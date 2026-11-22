# Dev5D3-F — Intelligent Archive Update Comparison

## Goal
Expose one read-only comparison of **installed record**, **downloaded archive identity**, and **latest online release** per supported dependency, without turning uncertain labels into installation authority. Preserve the clean archive-first GUI and independent online update workflow.

## Facts observed
- Parent: desktop-approved Dev5D3-E2 `2d52c42ae71bcc0a106391305e497446bf1cec52`; original worktree was clean when this branch began.
- Game-root Cyberpunk records include per-Nexus-component archive names and file lists, but not authoritative installed release hashes. Legacy UEVR, KHARVOX, Subnautica and Valheim records generally do not identify an installed release. Installation timestamps alone cannot identify versions.
- Archive scans provide recipe-pinned SHA-256, or sometimes official GitHub release SHA evidence. Unverified Nexus filenames are only hints. Online Updates are checked separately through the existing GitHub/Nexus worker and may use cached GitHub results; Nexus requires an API key.
- Saved scans, custom folders, and current data are user-owned. The current development preview already has multi-folder scans; no restoration or migration was requested in this milestone.

## Proposed defaults
- A single collapsed **Compare versions** disclosure beneath the existing five-column archive table. On opening it scrolls the evidence into view; expands a separate five-column read-only table, leaving primary review actions untouched.
- Installed: **Recorded x.y.z** when a recorded Nexus component archive filename contains a recognizable version, with explicit caveat that installed bytes are not verified; otherwise **Hub record · version unknown** or **Unknown**. No version inference from install timestamps or tested compatibility baselines.
- Downloaded: show exact pinned SHA-256 identity and its explicit recipe release tag when known; official SHA-256 tags as review-only; ambiguous, stale, missing, mismatched and filename-only archives explicitly marked. A filename suggests newer/older only with a strict mod-id version match and is **never** verified.
- Online: show only results from the separate Updates refresh. Resolve components by exact Nexus mod ID or uniquely mapped, typed GitHub recipe target. No broad repo/name guessing across paired UEVR assets. Missing key, failed refresh and no refresh remain unavailable/not checked.
- Comparison descriptions never enable installation. Existing full verified-set review, blocked recipe pins, profile backup/recovery and KHARVOX compatibility gates are untouched.

## Decision needed
None for offline implementation: the user explicitly requested starting Dev5D3-F and retained all prior no-live-install constraints. Desktop acceptance is required before calling the milestone user-approved.

## Scope
- New pure presentation model `vrhub/archive_update_comparison.py`.
- Add a collapsed comparison disclosure and read-only table to `vrhub/downloads_gui.py`, preserving all existing archive checklist columns and optional manual pickers.
- Feed it the **already available in-memory** Updates results from `vrhub/gui.py`. It issues no new HTTP request and does not trigger scans.
- Register the comparison table with the existing Hub-owned column layout helper. No format/schema changes to scan history, installation records or preference files.
- Dedicated unit/GUI regression tests and nine-game disposable KDE GUI harness.

## Safety/rollback
- New worktree/branch; parent checkpoint retained; no changes to real game files, installed mods, launcher/bridge, Proton prefixes, Nexus API key, archive downloads, original preview scans, preferences or state.
- No live extraction, download, update, install or auto-rollback. No automatic release/compatibility approval. Unexpected installed state and ambiguous source mapping remain unknown.
- Roll back code via parent `2d52c42`. Existing scan history and saved config remain untouched.

## Tests
- Focused suite including existing downloads/updates/table-layout tests: 71/71 passed.
- Full final regression suite: **1,025 run, 1,024 passed, 1 skipped**, no failures.
- Read-only comparison model tests cover pinned vs official SHA identity, Cyberpunk recorded vs filename-only hints, typed UEVR source matching, unavailable Nexus key, unknown installed records, tampered/stale scans and blocked pin mismatches. No need to access actual game files.
- Nine-game isolated KDE GUI harness using a disposable copy of the current preview store: **191/191** passed. Original archive table remains five columns, read-only comparison defaults collapsed, opens/scrolls into view and closes, switching games resets prior online context, existing install action state unchanged. Rendered Cyberpunk, Fatekeeper and Valheim screens inspected at 1630 x 1060. GUI sample latest `v0.11.3` for Valheim was **synthetic test data**, not a claimed real upstream update.
- Original shared preview data at final prelaunch review: state `ed2884a7ada0ec0364c32d86215fbae0f972fbb0530ea14a416c8e054089d16c`, scans `e94fc50fd3cd6ce56d4174a85c099e0fd995309262f251e2815c1f269d1e5dc1`, folder preferences `05c377e3b3d1beabb9844ee55fbaef822fedbe0ac940e5ac236562e5e3ecefc0`; exact values checked against starting state and no tool-driven changes.

## Desktop acceptance
- Nine-game preview, comparison collapsed by default and hidden for guide-only Skyrim, expansion scrolls to table; correct installed record/unknown distinction, downloaded SHA/release labels and online Not checked.
- After user-initiated **Refresh update status** on Updates, only supported uniquely mapped online values appear. No update check is initiated by expanding the disclosure.
- Invalid/stale or mismatched archives remain blocked; no changes to installed state or to original install-review button behavior.
- After switching games and restarting the preview, saved scan history and per-game archive folders remain intact.

## Deferred
Capturing cryptographically attributable installed per-package versions during a future **safe install**, real mod update/compatibility validation, automatic download/installation, VR gameplay, publication and live game modifications. An unverified installed release remains **Unknown** even if a game works in VR.
