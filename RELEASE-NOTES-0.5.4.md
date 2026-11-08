# NAnnersVRhub 0.5.4

Release version: **0.5.4**. Intended tag: **v0.5.4**. This document was prepared before publication.

This release adds development-only save backup/recovery, safer installer recovery and an accessible Hub rollback control. The existing nine game profiles and separately installed KHARVOX bridge remain in place.

## New features

- Development save recovery for all nine bundled profiles, hidden until enabled through Tools each session. Select the active target and source explicitly; the Hub never chooses a save by newest date or synchronizes progress automatically.
- Back up current saves without restoring anything, add a note and browse snapshot history with game/version/date/file-count labels.
- Compare added, changed, removed and unchanged files before whole-folder restoration. Inspect source and target summaries side by side, and preview Undo last restore with a fresh recovery backup.
- Remember custom source/target folders per game, with explicit selection and a Forget remembered folders control.
- Find Skyrim VR saves in base-game and MO2 shortcut prefixes, plus MO2 profile-local save folders where present.
- Hub updates now offers Roll back to [version], confirmation and Restart Hub. Previous application files are verified; missing/corrupt releases and stale confirmations block activation. The independent terminal recovery manager remains available.

## Fixes and clarity

- New PAK installs retain pre-existing files and restore them on uninstall. Changed files or missing/altered original backups block removal before modification. Recorded reinstall requires removal first.
- Game-root install transactions retain recovery copies until state commits; failed state writes roll back, and incomplete rollback reports retained recovery locations. Installer records use atomic replacement.
- Save restore binds reviewed paths to directory identity, rejects redirected/replaced source or target folders and checks again during preparation.
- Ordinary selection of a managed recovery copy checks its original recorded hashes, matching the integrity safeguards used by Undo. Missing or unconfirmed records remain blocked; existing files are preserved.
- Recovery discovery selects the 128 most recent backup sets by creation time, combines legacy/current DOOM sets before applying the limit and retains all copies belonging to the selected sets. Omission notices explain limits; no backups are automatically deleted. Missing creation dates use an explained folder-time ordering fallback, which does not establish save progress.
- Restore blocked — backup verification needed replaces ambiguous review wording for unusable backups. Details distinguish missing/unreadable records, unconfirmed preparation, wrong game and hash failures. There is no manual approval override.
- Save-location discovery shows observed dates/counts for unreadable or unrecognized save sets without authorizing restoration. DOOM metadata wording appears only for DOOM; Skyrim date display excludes Steam metadata.
- Development save recovery layout reflows status messages and instructions, preserves visible actions through scrolling and uses side-by-side source/target summaries. **Only that development window** has 70%, 80%, 90% and Custom sizing, with an 80% default and actual width/height percentages. Other Hub windows do not gain these controls.

## License

The Hub's original code is now explicitly licensed under GNU GPL version 3 only (GPL-3.0-only). LICENSE, package metadata and source notices identify the terms. The existing MIT bridge installer retains its original license and notice. External runtimes, dependencies, mods, profiles and game files keep their own terms. This licensing change does not combine the Hub with Kaon or transfer project ownership.

## Validation and scope

The accepted RC1 passed 598 automated tests. The user reported the RC1 desktop check passed on November 7, 2026 (America/Los_Angeles), following explicit dev23 confirmation that declining rollback, accepting rollback and Restart Hub worked. Earlier reports cover save backup, comparison and recovery UI behavior. The final stable build passed 598 tests plus managed upgrade and two-way rollback checks from 0.5.3 and RC1, retaining nine recipes and seven sentinel files. Evidence is recorded in VALIDATION-0.5.4.md; no fresh gameplay success is inferred from release preparation.

Game installs, saves, mod inventories and gameplay-test history remain separate from app activation. Application rollback is not a rollback of user data or mod-install metadata. Existing PAK backups absent from legacy versions cannot be reconstructed; remove new pak-1 installs using a compatible Hub version before rolling back to a version that cannot understand that metadata.

## Remaining limits

- Development recovery validates file sets and integrity, not binary save correctness, gameplay progress or game/mod compatibility. Close games/launchers and stop cloud synchronization before replacement. Only DOOM metadata is interpreted; other games mostly use file modification dates.
- Two earlier medium-priority installer findings—profile replacement failure recovery and stale files after injector replacement—remain deferred. This release does not claim to fix them. Power-loss recovery and a general lock across all external writers are also not implemented.
- Controller/headset and gameplay compatibility reports remain dated, setup-specific evidence. The experimental DOOM route and its separate bridge are not certified for every runtime, launcher or machine.
- RC1 desktop acceptance passed. Final stable publication approval remains pending. The actual public-endpoint 0.5.4 update test follows publication and is not claimed as already passed.

AI assistance was used for development, documentation and troubleshooting alongside hands-on user tests and automated checks. Software may still contain defects.
