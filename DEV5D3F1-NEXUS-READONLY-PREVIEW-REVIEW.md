# Dev5D3-F1 — Read-only Nexus credential reuse in desktop preview

## Goal
Fix the desktop-approved Dev5D3-F preview showing "Unavailable / Nexus key needed" solely because its isolated credential file is absent, while preserving production credentials and every game/install safety gate.

## Facts observed
- Approved parent commit: `dae64e75ae6393a3d07d74512123ee421f759260`, on `dev/0.5.5-archive-update-comparison`.
- Existing Nexus credential at `~/.config/vrhub/nexus_key` is a normal regular file, owner current user, permissions 0600. Its value was not printed, copied, added to a command argument or recorded in tests.
- The development preview used `VRHUB_NEXUS_KEY_FILE=~/.local/share/nannersvrhub-development-preview/test-nexus-key`, which does not exist. The runtime otherwise inherited an isolated XDG config root, making the ordinary credential path unavailable.
- Nexus update checks are read-only lookups via the existing Updates refresh; GitHub lookups do not require this credential.

## Scope and defaults
- Add explicitly opt-in `VRHUB_NEXUS_READONLY_KEY_FILE` fallback to `updates.get_key()`. Existing `NEXUS_API_KEY` / preview-specific private key priorities are preserved. The fallback is read with O_RDONLY | O_NOFOLLOW and checked for regular-file type, current user ownership, private permissions, bounded size and UTF-8. Unavailable or unsafe sources return no key.
- Set that fallback path only in the `--show` desktop-preview launcher. Production/runtime launchers don't set it. Existing preview key destination stays isolated; no key bytes are copied or printed.
- Prevent saving or removing credentials when the writable key path is the read-only fallback or a symlink. GUI key management button stays disabled in the preview under its existing safety controls.
- Update preview title and key button explanation; leave all other archive/installation logic unchanged.

## Safety and rollback
- Isolated new Git worktree `~/Projects/NAnnersVRhub-0.5.5-dev5d3f1` on `dev/0.5.5-preview-nexus-readonly`; preserve parent worktree and all older checkpoints.
- No live install, transfer, extraction, mod/profile/Proton/game save modification; no preview state or scan reset.
- The real Nexus key file's size, mode and mtime were unchanged when the effective key was verified; the preview credential file remained absent.
- Rollback by returning to the approved parent; never delete or replace the original Nexus key.

## Tests
- Targeted test suite: 39/39 passed. Fixture-only tests check private-file fallback, malformed/missing/oversized/insecure/symlink sources, override precedence, rejected writes/removals to read-only source, preview-only writes and a mocked Nexus update lookup.
- Full regression: **1,034 run: 1,033 passed, 1 skipped**.
- All nine-game isolated GUI harness checks: **191/191 passed** using a disposable copy of preview data and no real credentials.
- Actual device read-only resolution: **PASS**, source metadata unchanged and no preview key copy. No actual live Nexus API response was verified at checkpoint time.
- Existing preview state and scans checksum unchanged at checkpoint: state `ed2884a7ada0ec0364c32d86215fbae0f972fbb0530ea14a416c8e054089d16c`; scans `9df00d61e906c4588b4370ca2a95a2129a4e944a613ef9da9ad549d548756038`; preferences `05c377e3b3d1beabb9844ee55fbaef822fedbe0ac940e5ac236562e5e3ecefc0`.

## Desktop acceptance
- Open Dev5D3-F1 desktop preview.
- Select a Nexus-based game (e.g. Cyberpunk 2077) and choose Updates → Refresh update status. Nexus no-key warning should no longer be caused by the absent *preview* credential; other API errors/rate limits remain possible and require investigation.
- Install / Update → Compare versions may show online values only after an eligible update lookup. No live-install action is enabled.
- Scans, archive folders and other game workflows remain unchanged.

## Deferred
Confirmed live Nexus API server acceptance / rate-limit status, future installed-version provenance, actual game updates and release publishing.
