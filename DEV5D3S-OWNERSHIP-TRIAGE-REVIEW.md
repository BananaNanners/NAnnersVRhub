# Dev5D3-S — Non-Destructive Ownership Reconciliation & Modified-File Triage

## Goal
Explain existing installation ownership discrepancies and tracked-file SHA-256 differences without modifying games, downloaded ZIPs, profiles, historical backups, or Hub ownership records. Start with Valheim and Subnautica's concrete differences and preserve separate guidance for legacy Cyberpunk and UEVR profile records. Keep NAnnersVRhub's archive-first UI clean and use its existing Verify installed files and Review replacement safety actions.

## Facts observed
- Approved parent: desktop-approved Dev5D3-R, commit `6c002b8f177b673decf3e90e34f45c8d7607cf5c`, clean at fork; Dev5D3-Q and all older approved worktrees remain intact.
- On-demand **read-only** verification of the existing development-preview state reported:
  | Game / package | Prior scan outcome | Recorded file-level differences |
  |---|---|---|
  | Valheim BepInExPack loader | 22/23 matched | `BepInEx/config/BepInEx.cfg` (Modified) |
  | Valheim VHVR | 110/112 matched | `valheim_Data/Managed/UnityEngine.SpatialTracking.dll` and `valheim_Data/Managed/UnityEngine.XR.LegacyInputHelpers.dll` (Modified) |
  | Subnautica BepInExPack loader | 35/36 matched | `BepInEx/config/BepInEx.cfg` (Modified) |
  | Subnautica VR package | 9/9 matched | No differences at that on-demand check |
- These four modified files differ from previously recorded SHA-256 hashes, but that **does not** establish why they changed, whether they are intentionally customized, whether they represent a different release, or whether the associated games/mods work.
- Cyberpunk's older component manifest has no current `gameroot-2` managed-file hash evidence. Fatekeeper's profile locator was unresolved in the earlier R audit; Hogwarts Legacy's expected directory was found without complete ownership. Installed-file check cannot safely upgrade those records to trusted ownership.
- R's read-only real-installation audit is a point-in-time directory/record check. N/O/P's synthetic rollback demonstrations and Q's unified plan do not authorize actual installation.

## Proposed defaults
- New `vrhub/ownership_triage.py`: **pure, no-I/O**, per-game and per-dependency analyzer of the existing R audit and an optional already-completed on-demand installed SHA result. Never open or hash files, look up private state, infer a release from modified bytes, adopt legacy paths, mutate state, propose executable repair, or return an authorization token.
- A changed `.cfg/.ini/.json/.toml/.yaml/.yml/.xml` is a **possible configuration customization (cause unverified)**. A changed `.dll/.exe/.asi/.so/.bin/.pdb` is **unexplained binary drift**. Missing, unsafe, unverifiable, and other modified files have distinct review guidance. This is classification only; no cause, integrity guarantee, or permission is inferred.
- Include only bounded, validated **relative file paths** from the existing safe verifier. Refuse absolute paths, traversal, casefold duplicates, suspicious issue lists, cross-game data, false Verified summaries, forged live permissions and oversized/unbounded result sets. Preserve a count of additional unmatched entries omitted by the verifier's capped output.
- Prior matching hashes still mean **historical match only**. Unverified ownership or unresolved game/profile locations take precedence over any apparent file-level success. Missing integrity results remain **not checked**, never implicitly clean. Manual workflows remain manual, but missing game location is a visible blocker.
- Reuse the existing Verify installed files text field for tentative per-file explanations. The existing Review replacement safety (read-only) report adds an **OWNERSHIP RECONCILIATION & MODIFIED-FILE TRIAGE — READ ONLY** section after R's audit and before Q's unified review. No additional button or production tab.
- Maintain the six-fixture preview-only synthetic rollback rehearsal exactly as approved; do not operate on real game paths or treat fixture success as compatible live updates.

## Decision needed
The user explicitly started Dev5D3-S after approving R. Conservative read-only defaults are suitable for this milestone. **Real KDE desktop acceptance is still required.** Separate authorization is needed before any repair, version overwrite, state migration, manual adoption or live update.

## Scope implemented
- `vrhub/ownership_triage.py`: bounded, fail-closed evidence classification, per-component ownership/tracked-file differences, next review steps, explicit absence of update/migration authority and no file I/O.
- `vrhub/downloads_gui.py`: append human-readable tentative explanations to the existing explicitly triggered integrity result; the existing on-demand replacement safety worker adds pure triage of the preceding R audit/optional verified-file check; the existing safety details include review steps. Old update controls, scan policy and installer gates unchanged.
- `tests/test_ownership_triage_s.py`: synthetic and Qt tests for all nine recipes/27 dependencies, Valheim's 1 config+2 binary differences, Subnautica's 1 config and 9 prior matched VR files, legacy Cyberpunk and UEVR ownership, missing game/profile locations, no-scan unknowns, capped outputs, unsafe paths, cross-game and duplicate evidence, no live actions and actual Qt review lifecycle.
- `tests/manual_launcher_dev5d3s_preview.py`: inherits all approved R nine-game KDE checks and adds a read-only triage for every component, a synthetic Valheim config/binary integrity report and a synthetic Fatekeeper prior-verified-but-still-blocked whole-profile report. Six previous temporary fixture rollback rehearsals remain present.

## Safety/rollback
- Isolated worktree `~/Projects/NAnnersVRhub-0.5.5-dev5d3s`, branch `dev/0.5.5-ownership-reconciliation-triage`, forked from the approved R `6c002b8` checkpoint.
- No installed game, mod ZIP, Steam/Heroic prefix, UEVR profile, user config, saved game, real backup, personal Nexus credential, original scan or folder settings changed. The explicit read-only installed SHA verifier was called to collect evidence; the new triage module itself never reads files.
- The four modified paths above are never embedded as live permissions or automatic resolution. Not a repair or reconciliation **mutation**; only diagnostic review guidance. No historical SHA-256 value is overwritten, no untracked component is silently adopted, and legacy ownership remains unverified.
- Existing overwrite refusals, backup/recovery protections and live-execution safety gates remain unchanged. Roll back source simply by returning to the approved R worktree and commit; never delete saved user data/history.

## Tests
- Focused S+R+Q automated tests: **70/70 passed**. Initial synthetic manual-game missing-root expectation failed; triage was updated to prioritize unresolved locations, and all tests rerun green.
- Full regression discovery: **1,337 tests run; 1,336 passed, one skipped**, zero failures.
- Final disposable nine-game KDE harness: **470/470 checks passed**. A synthetic Fatekeeper acceptance expectation was corrected to require `historical_match_only` (recorded root+prior matched hash), while retaining zero live update authorization; rerun green.
- Rendered KDE screenshots inspected: synthetic Valheim modified-file explanations, Fatekeeper triage text viewport, and preserved Cyberpunk six-scenario offline rehearsal. No new production button or control overlap.
- Original shared preview state, saved scan history and custom archive-folder preference SHA-256 digests remained unchanged across checks. Nexus key stays read-only and is never copied.

## Desktop acceptance
1. Open the Dev5D3-S preview. Normal on-demand Downloads + optional game folder scans, saved archive inventory, Nexus online Updates, and per-game dependency rows remain intact.
2. For Valheim and Subnautica, click **Verify installed files** on demand. Confirm each reported BepInEx.cfg is described only as **possible local configuration change**, and Valheim's Unity/XR DLLs as **unexplained binary differences**. No automatic repair, rollback or hash rewrite appears.
3. Expand Install / Update → Compare versions → **Review replacement safety (read-only)**. Verify **OWNERSHIP RECONCILIATION & MODIFIED-FILE TRIAGE — READ ONLY** with per-component next steps; old-file differences never become ready-to-update decisions.
4. Check Cyberpunk's legacy ownership still needs manual reconciliation, Fatekeeper/Hogwarts UEVR injector/profile distinction remains intact, and unresolved game/profile locations cannot become automatic ownership.
5. Confirm prior hash matches are **not** current update permission; fresh backups, game-stopped locks, real compatibility, production recovery and separate approval are still unresolved. Switching games invalidates the prior review.
6. The existing six-scenario **TEST FIXTURE ONLY** rehearsal, KHARVOX tools, manual archive review, version comparison, backup/recovery and installer safety gates remain intact. No actual installed files were modified, and the GUI remains readable without overlapping controls.

## Deferred
Determining the *actual* cause or desirability of each modified file; independently inspecting mod release provenance and game/Proton compatibility; reconciling outdated installed ownership with user approval and verified fresh backups; safe manual ownership adoption UX; complete real pre-update backup, process lock and tested rollback; enabling any real update; Quest headset game validation; publishing a release.
