# Dev5D3-Y — Player-First GUI Simplification & Installation Workflow Cleanup

## Goal
Restore a direct player task flow: choose a game, scan downloaded mod ZIPs and required dependencies, review the intended installation, then verify/troubleshoot. The preview's sidebar, archive scanning, Update tab, installer/recovery safety guards and game-specific actions should remain. Do not present developer staging rehearsals or duplicate version tables as normal install steps.

## Facts observed
- Desktop-approved parent: Dev5D3-X commit `1f6c9f5431c9a338c2287eb5b5b2bb379eeb9cfc`, worktree clean when forked.
- Installed stable release 0.5.4 has two main areas and three game-detail tabs; on Fatekeeper, direct Install mod file / Install profile / Preflight / Launch game buttons are visible, although the controls are crowded.
- Preview Dev5D3-X has a sidebar and seven organized game tabs, with dedicated Updates, game-specific archive-first Install / Update and recovery pages. It has better visual organization, archive detection, source links and backup safeguards, but the guarded Review installation button followed the large archive table, technical comparison, and integrity controls, often below the visible viewport.
- The dedicated Updates page already lists installed and latest versions. Its `ModUpdatesPage` provides separate online refreshing. The installation comparison duplicated versions and showed extra developer-facing evidence and conditional planning warnings.
- `Review replacement safety (read-only)` and `Rehearse unified update staging (TEST FIXTURE ONLY)` are **not** necessary steps to trigger the existing game install-review handlers. The rehearsal is injected only by the development-preview harness and only tests disposable synthetic data.
- The old install-review dispatcher (`_request_install_review` and backing handlers) already revalidates current saved scan identity, chosen ZIPs, pins, backups and required game routes. Moving the existing action does not authorize additional installs.

## Proposed defaults / implementation
- Move the exact existing `review_actions` widget (guarded primary Review installation / Choose archive / Install verified dependencies button and manual fallback), plus its next-step guidance, above the dependency table. Keep backup/conflict warnings above the action. Put scan-age and saved-scan-count context below the action instead of pushing it off-screen.
- Retain `Archive folder` + `Scan local archives`, original archive-first checklist with explicit statuses/source links, `Verify installed files`, the separate `Updates` tab, and all native install-review routing. No duplicate new install control.
- Rename the normal `Compare versions` disclosure to `Advanced diagnostics`; move it after the installed-file check. The internal read-only version comparison and readiness model remains calculated for existing safety/legacy tests, but the duplicate version table, comparison summaries and readiness labels are **hidden** from the player UI even when Advanced diagnostics expands. Updates remains the sole visible installed/latest version comparison.
- Keep the manually requested read-only `Review replacement safety` diagnostic inside Advanced diagnostics with the existing transient safety worker and detailed reports. Do not call the report on every scan/game switch. Normal install review remains connected to its original safety guards; this milestone does NOT introduce new automatic real replacement authorization.
- Remove outdated player guidance referring to retired `More installation tools`, and simplify the archive description to explain scanning and reviewing in gamer terms.
- In the development preview only, keep synthetic transaction rehearsals behind **Tools > Enable development tools** AND an expanded Advanced diagnostics panel; they are invisible to ordinary preview users and never appear in the normal production app.
- Preserve exact release/source, profile compatibility, untracked-file ownership and previous backup restrictions. No new live transaction, install, backup or restore executor.

## Decision needed
User explicitly started Dev5D3-Y after acknowledging the stable-vs-preview usability audit. This approved UI scope is implemented in a separate branch. **Manual KDE desktop acceptance remains pending.** No approval has been given to rewrite production backups, replace real mods or enable the unfinished live update executor.

## Scope
- `vrhub/downloads_gui.py`: reorder original guarded action and scan context before the archive table, rename/relocate advanced safety diagnostics, hide redundant display-only version evidence, keep separate Updates source authoritative, simplify outdated next-step help. No change to installation dispatch logic or game files.
- `tests/manual_launcher_dev5d3y_preview.py`: isolated X-derived GUI preview that disables live installs/transfers, respects original shared preview state and read-only Nexus key, and hides synthetic rehearsal unless Tools > Enable development tools is explicitly toggled. Nine-game desktop checks and a 1280x720 first-viewport action visibility assertion with renders.
- `tests/test_player_first_ui_y.py`: direct game-profile layout checks; advanced diagnostic isolation; no implicit safety inspection; original pinned-package install-review dispatch; stale/missing dependency refusal; separate online Update state.

## Safety / rollback
- Worktree `~/Projects/NAnnersVRhub-0.5.5-dev5d3y`, branch `dev/0.5.5-player-first-ui`, created from approved X commit `1f6c9f5`. The X checkpoint and all earlier worktrees remain unmodified and usable for source rollback.
- Existing stable installation `~/.local/share/nannersvrhub/releases/0.5.4-...` and user game installs stay untouched. No ZIP is extracted; no Nexus credential is copied; no saved archive scan, selected folder, SHA record, backup or Proton/Heroic/Steam state is modified by development.
- UI acceptance harness tests use disposable *copied* preview state and synthetic files only; the real desktop preview shares the established development-preview state without resetting or migrating it.
- All original safety and recovery gates remain unchanged; no live update transaction or game runtime compatibility is claimed.

## Tests
- Focused user-interface and installation/safety tests: 48/48 passed.
- Full regression discovery: **1,482 run; 1,481 passed, 1 skipped; 0 failures**.
- Final nine-game KDE isolated harness: **129/129 checks passed**.
- Actual 1280×720 KDE screenshot: Fatekeeper's existing `Choose archive` primary control lies within the initial game viewport (button vertical pixels 468–504, viewport height 518), without scrolling. No duplicate version comparison or fixture action is visible by default.
- Development-only rehearsal: hidden in normal preview and while Advanced diagnostics alone is expanded; visible only with both Tools development mode and Advanced diagnostics; still six synthetic rollback rehearsals and five synthetic payload classification cases, no live game changes. Switching games clears prior evidence.
- All three protected preview state, saved scan and archive-folder preference hashes remained the same throughout development. The Nexus key is only read, not copied.

## KDE desktop acceptance
1. Dev5D3-Y preview opens normally; the sidebar, all nine games, archive scan folders and saved scans remain unchanged. On Fatekeeper, the action to choose/review ZIPs is visible near the scan controls before the big dependency list; check at normal window size.
2. The Install / Update page retains one clear guarded action plus manual selection when needed, and the archive checklist still shows each required ZIP, status, stage and trusted source. Ambiguous/stale/missing archives still cannot bypass review.
3. Updates remains the place for installed/latest versions and online status. In Install / Update there is no Compare versions button or duplicate version table.
4. Verify installed files remains available; Advanced diagnostics stays collapsed by default and, when opened, contains the read-only replacement risk report, not a second version comparison. No surprise background safety worker.
5. Rehearse unified update staging is absent from normal preview. Optionally check Tools > Enable development tools then Advanced diagnostics: it appears as **TEST FIXTURE ONLY**, runs synthetic cases, and never installs. Switching games clears the result and disabling dev tools hides it.
6. Existing Setup Guide, Compatibility/Preflight, KHARVOX, UEVR profile review, rollback/backups, source links and installer protections still function; controls fit without overlaps. No real files, mods or saves are modified.

## Deferred
Incorporating newer read-only preservation evidence inside a separate, explicitly approved **real** installation transaction; more concise gamer-friendly warnings per dependency; true supported-game integration tests on intentionally disposable installs followed by separately approved live game testing; authenticated Nexus source provenance; future release publish.

## Desktop acceptance feedback — Dev5D3-Y1 correction
- User reported 4 of 6 original Y acceptance checks passed; 2 need correction, so **Y remains pending desktop approval**.
- Fatekeeper's current selected scan did not show the exact **Choose archive** label expected by the checklist. That was a mistaken fixed-label acceptance requirement: the original _primary_action() depends on archive selection status and may instead return Review installation or another contextual action. Cyberpunk shows Choose archive when the particular dependency needs a choice. No installer decision logic, archived scan, or version evidence was changed just to match the test wording.
- **Confirmed real preview bug:** the inherited LauncherPreview.disable_mutations() unconditionally disabled the QMenu QAction Tools > Enable development tools. Old Y tests used QAction.setChecked(True), which can set a disabled action and falsely passed. The real Tools menu remained inert.
- The X synthetic rehearsal widget was also left as an outer-page sibling after Y moved the Advanced diagnostics panel, so even if enabled it could appear far away. Y1 reparents this **preview-only** widget inside the diagnostic panel, below the explanatory note.
- Y1 overrides only the preview's disable_mutations() to run all inherited safety restrictions and re-enable this reversible UI QAction. Every real installer, transfer, recovery, save edit and live update button stays disabled. The QAction menu now announces its current mode in the status bar and scrolls the visible fixture control into view after Qt finishes rebuilding the page.
- Acceptance harness triggers the actual Tools menu action, not setChecked(), and verifies its enabled/checked states, status feedback, visible in-viewport fixture, bounded non-live rehearsal, and disabled mutation controls. Prior tests and historical state are preserved.
- Corrected manual check #1: verify **the correct context-sensitive installation action**, whether Review installation, Choose archive or a scan-required state; do not require Fatekeeper to display one fixed label or change verification evidence to force it.
- Corrected manual check #2: in Install / Update, open Advanced diagnostics, then use Tools > Enable development tools; the fixture button appears inside Advanced diagnostics and the status bar says Development tools ON. Using Tools again hides the fixture; no real game changes.
