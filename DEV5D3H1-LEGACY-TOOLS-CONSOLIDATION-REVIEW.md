# Dev5D3-H1 — Legacy Installation Tools Consolidation

## Goal
Retire the redundant "More installation tools" drawer on Install / Update, without losing the legacy controls' genuinely distinct capabilities or creating duplicate buttons. Preserve all live installation, source hash, backup, recovery and compatibility safety gates.

## Facts observed
- Parent: desktop-approved Dev5D3-H checkpoint 7da025123e3310f996dc7e31207b034c47e3667e. Parent worktree clean at fork.
- The old "Verify mods" is a legacy **component presence/readiness** check, not the new per-file SHA-256 integrity verifier. It returns an overall readiness report including required and optional/later components.
- "Choose archives manually…" is still a guarded contextual escape hatch for Cyberpunk batch mod selection and UEVR profile cases. Missing, stale or blocked archives stay blocked by the existing manual-review gate.
- "Inspect archive…" is a separate read-only arbitrary ZIP staging inspector; "Inspect selected archive" is already a native, contextual action on the archive page.
- "Download and verify" is already owned by an archive-page transfer row with pinned-SHA and explicit confirmation gates. The old drawer inappropriately reparented its button into the drawer.
- KHARVOX's choose-folder, runner preparation, and bridge-package import actions are DOOM-specific; their existing handlers and gates must remain available on that game's Compatibility page.

## Proposed defaults
- Remove the general installation-tools disclosure from any visible layout. Retain a non-visible compatibility container only for old handler object identities; it is not expandable and is never shown.
- Keep the preexisting contextual manual-review button in the archive page footer. Keep the preexisting selected-archive inspection button in its own review footer.
- Add a single "Inspect another archive…" action inside the already-existing Archive folder menu for gameroot, bepinex and ervr games, invoking the unchanged old inspector. Its action is hidden for unsupported games and disabled while archive scanning/transfers are in progress.
- Keep the existing verified-download button in the archive-page transfer row, without relaxing its eligibility or confirmation gates.
- On explicit "Verify installed files", include the legacy required-mod presence summary, clearly labelled **presence only; not SHA-256**. Separate this from the recorded-hash integrity counts and show required/optional missing components as review details. Unsupported or failing presence checks remain Unknown.
- Rehome the three DOOM/KHARVOX specialist buttons into the existing Compatibility disclosure. There is no extra new disclosure or button.

## Decision needed
None for this implementation. The user approved the described Dev5D3-H1 design and explicitly requested development. KDE acceptance remains pending; no live installation authorization has been granted.

## Scope implemented
- vrhub/gui.py: retire visible Install tools drawer; keep dormant internal handler objects, preserve manual fallback and original archive review button placement, append contextual manual archive inspector to the existing archive menu, move KHARVOX buttons to Compatibility.
- vrhub/downloads_gui.py: one-click integrity worker also invokes the existing read-only hub.verify presence check on demand and reports it separately, with unknown/failure handling and no installation action state mutation.
- tests/test_legacy_tools_h1.py: explicit Qt regression of no visible old drawer, manual fallback, menu inspector, KHARVOX placement, readiness/integrity separation and no result leakage.
- Update old UI-layout assertions in test_button_consolidation.py, test_visual_polish.py, and test_kharvox.py to the approved new interface; their functional safety assertions continue.
- tests/manual_launcher_dev5d3h1_preview.py: disposable nine-game KDE harness extending prior established Dev5D3-H fixtures.

## Safety / rollback
- New isolated branch dev/0.5.5-legacy-install-tools-consolidation at ~/Projects/NAnnersVRhub-0.5.5-dev5d3h1. Parent and all historical checkpoints unchanged.
- No installation, extraction, file replacement, Nexus credential copy, package download, profile write, user scan restoration, backup deletion or new state schema.
- The existing install review dialog confirmation, archived SHA and recipe pin checks, Cyberpunk legacy backup refusal, UEVR profile full-directory backups, KHARVOX bridge guards and recovery remains in place.
- Old generic presence "Ready" continues to mean only required files *appear present*, not that installed bytes match. A successful SHA-256 comparison also does not establish VR runtime success.
- Revert source to parent 7da0251; retain all persistent state and past source history.

## Tests
- Old/new focused UI, manual review, installed integrity and KHARVOX cases: 104/104 passed after updating intentionally obsolete old-drawer assertions.
- H1-specific Qt tests: 8/8 passed, including a real worker click with isolated, mocked readiness results and preserved install action state. Additional H1+KHARVOX+install focused run: 44/44 passed.
- Final full suite: 1,074 run; **1,073 passed, 1 skipped**, no failures.
- Final nine-game isolated KDE GUI verification: **305/305 passed**. Uses private copied preview state and synthetic disposable integrity fixtures, never a live install. Rendered Fatekeeper, Cyberpunk and DOOM Compatibility screens at 1630×1060 visually inspected.
- Original preview state, saved archive scans and folder preferences have not been reset or edited by the tests.

## Desktop acceptance
1. The old More installation tools panel is absent; the main Install / Update layout remains clean.
2. Manual selection is only offered for games/conditions that need it; when needed, it still routes into existing safety review.
3. Selecting a supported dependency allows Inspect selected archive; Archive folder menu also includes Inspect another archive for supported games, not unsupported UEVR/guide games.
4. Verify installed files reports both historical SHA-256 matching and separately labelled required-mod presence; details appear only when attention is needed.
5. DOOM/KHARVOX actions remain discoverable in Compatibility, and are absent for unrelated games.
6. Nexus Updates and version comparison remain separate and functional; local scans, folder preferences, backups, recovery and all live installation gates remain intact.

## Deferred
Mod upgrades, automatic repair, automatic archive matching, new install permissions, standalone deletion of legacy handler APIs, real VR gameplay acceptance, and publication.
