# Validation — October 21, 2026

- 15 standalone installer policy checks passed (no Wine/game/headset/network).
- 54 unchanged lab engine host tests passed.
- 402 Hub tests passed with Qt offscreen, including the shared installer tests and managed upgrade/restart/rollback coverage.
- The exact upstream 335059640-byte base archive was downloaded and SHA-256 checked: 62ff4b2750180723cc00538608fe687e21d1d91a31ef64ce1a7c9f46c3db310b.
- All seven baseline file digests matched the user-tested lab inventory.
- The installer downloader itself fetched and verified that release with its redirect/size/hash checks.
- A real empty-state installation using the pinned offline archive prepared the complete isolated runner. No selected Heroic runner was needed.
- Re-running install with a nonexistent archive reused the runner offline with all tracked module hashes unchanged.
- Real uninstall removed that owned runner while preserving a historical log and external save sentinel.
- All 94 lab payload files remain byte-identical to 0.1.6. The installer file is identical in the standalone project and Hub.

No Wine/OpenXR/headset/game execution occurred in the development container.
The prior user-reported dev9 Hub test passed rendering, head tracking,
controller input and stereo depth. The new installer/download button still
needs an on-PC check. GitHub publishing is pending; local CI configuration
has not been executed on GitHub. Tests do not establish compatibility for
other games, distributions, GPUs or headset models.
