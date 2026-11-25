# Dev5E6 — Fresh-install gameplay and scoped recovery authorization

Unreleased 0.5.5 development; November 24, 2026 (local time).
Baseline: 98c2c25dcdf54aeb6613278dd0a49c8f3637036e.
Global live installation/recovery gate remains closed. No release or push.

## Controlled installation and gameplay

- Test A: private /tmp/nanners-e6-test-SWZhQQ, synthetic Steam metadata and
  independent app 2186990 prefix; actual game files shared for native Steam
  launch. This was not a complete filesystem sandbox.
- Actual production transaction installed 111 files (8 injector, 103
  profile), including automatically fetched pinned Joeyhodge backend.
  Independent Test B installed the same payload and rolled it back, restoring
  its prior inventory and file hashes/modes; directory mtimes not verified.
- Proton CachyOS-11.0-100, portable .NET 6.0.36 Desktop Runtime (511 files,
  not MSI registered), game-bundled x64 Visual C++ redistributable.
- Native Steam launch and Protontricks 1.14.1 injector both verified by
  actual process WINEPREFIX. Steam Cloud disabled by player during test.
- First injection reached overlay but OpenXR returned -51; rendering froze.
  Game stopped via Steam; injector and lingering Test A start.exe required
  targeted termination. Normal shutdown failed in this attempt.
- Controlled relaunch added XR_LOADER_DEBUG=all; Quest 3 connected before
  launch. Native runtime loading and instance creation succeeded. Injector
  also received explicit host-side WiVRn manifest and loader diagnostics.
  Exact causal change remains unconfirmed. Do not claim a permanent fix.
- Player reported all nine gameplay checks passed: injection, OpenXR,
  no LuaLoader/backend error, stereo, tracking, both motion controllers,
  movement/combat and stability. Proton trace contains session creation
  and begin calls. Persistent DLSS FG warning despite disabled FG is
  player-reported; injector Vulkan swapchain/GDI warnings observed.
- Player reported all four normal shutdown checks passed following
  successful gameplay; OpenXRRadio exception not observed. Earlier
  exception root cause remains unconfirmed.

## Preservation and restoration

- Original launch options restored byte-for-byte. Steam Cloud restored
  enabled and Up to date (player confirmed); local sync state synchronized.
  Remote cloud contents not directly inspected.
- Final post-sync independent hash comparison: 7 original Fatekeeper
  files, 43 SLASHER files, 1 local cloud-cache file unchanged; no missing
  or added files in these inventories. Original injector, backend, UEVR
  user.config and stable Hub state hashes also matched baseline.
- No remaining test processes. Test saves remained separate; no live
  save restore needed. No full working-prefix or game-directory integrity
  claim. Original recovery backup retained in private recovery directory.
- Test roots and all prior temporary evidence retained. Selected 13
  gameplay/diagnostic/regression log files copied byte-for-byte into
  private persistent local evidence storage (1,562,554,866 bytes).
  Local folder: ~/NAnnersVRhub-recovery/Dev5E6-gameplay-evidence-qoQG5o
  Manifest SHA-256:
  a16853902e99b252b8ca172ca2740c3a8fbf3b1e11ce5cc81de00ba10e2c96d2
  Logs are not part of the Git repository. Backup is on same host/disk.

## E1 recovery provenance

- Scoped writer records exact durable journal digest in process-local
  registry before dependency writes; updates on each journal phase.
- Authorization and consumption require current scope identity, process
  identity, and trusted digest. Journal rechecked during commit/recovery
  and immediately before phase changes. Existing ordinary production gate
  and fixture routes unchanged.
- Six new tests: structurally valid unapproved journal, modification before
  approval, restart without registry, other process, old phase replay,
  interrupted recovering-phase resume. Existing rollback tests pass.
- Targeted suite: 65/65 passed. Full unittest discovery: 1625 total,
  1624 passed, one skipped, zero failures/errors, 34.215 seconds.
  Full log retained with gameplay evidence. No GUI source changes.
- Process-local provenance is deliberately fail-closed after restart.
  Historical A/B journals are not retroactively trusted. Persistent
  authorized recovery across restart is not solved; manual review required.
  No same-UID security boundary; cooperative locks/rechecks do not eliminate
  all possible races. Production recovery remains disabled.
- Remaining: restart-persistent recovery design, latest interactive KDE
  acceptance, production acceptance, packaging and remaining game tests.
