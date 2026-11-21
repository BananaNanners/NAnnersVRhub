# NAnnersVRhub 0.5.5-dev5C3a — UEVR Human-Readable Sizes

Scope: small display-only follow-up to approved Dev5C3 (02008c3).

- UEVR profile review now uses the existing shared decimal size formatter from install_review.py.
- New profile archive size and existing profile/backup estimate display as B, KB, MB or GB as appropriate.
- Hover over the overview for **exact byte counts** for both sizes.
- Read-only CLI review shows the backup estimate in human-readable units.
- Isolated Dev5C3a desktop preview uses a realistic 3.75 MB / 54.48 MB sample, and fixes a duplicate preview class that previously shadowed the intended read-only UEVR review handler.
- No installer, restore, backup, archive processing, game file, UEVR, Proton, save, or production Hub behavior was changed. Dev5C3's live-execution safety gate remains **closed**.
- Approved Dev5C3 remains unchanged; this follow-up lives in its own branch/worktree.

Verification:
- Full existing suite: **898 tests run, 897 passed, 1 skipped**.
- Dev5C3a isolated Qt preview: **99/99 checks pass** (including sample KB/MB/GB and exact-byte tooltips).
- Original Dev5C3 and production 0.5.4 checkpoints preserved.

Desktop acceptance:
- [ ] Window is clearly labeled Dev5C3a PREVIEW.
- [ ] Select Hogwarts Legacy > Advanced Tools > Review UEVR profile…, choose existing profile ZIP for blocked legacy review.
- [ ] Profile size and existing-directory/backup estimate use KB/MB/GB when appropriate.
- [ ] Hover overview to see exact sizes in bytes.
- [ ] Legacy blocker and disabled Apply remain intact; no live installation.
- [ ] Existing tabs and saved scans remain functional.
- [ ] User approves small UI correction.
