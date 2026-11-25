# Dev5F2A — DOOM installation workflow refinement

Baseline: 95b643ae31b373ac6c9fd39f57a77cb38385fbbf.

- Move the existing KHARVOX selection, runner installation and bridge import
  buttons to Install / Update. Keep test and launch on Overview; diagnostics
  on Compatibility. No duplicated actions.
- Display the required bridge 0.2.0 release page and installed payload status
  (missing, verified or review required). Status hashes files without importing
  the engine. Existing installer protections remain unchanged.
- Explain automatic bridge acquisition and manual custom archive fallback.
  Preserve original runner, version pins and historical gameplay evidence.
- Published bridge archive verified: 39406366 bytes,
  SHA256 26dcdbef5588336954676ce2c3023f8b17c11f0263f334610d124f4a514927d0.
- Actual automatic fetch and separate manual import passed.
- Fresh installer using empty test HOME and isolated state downloaded the
  pinned bridge and upstream base, verified both hashes, prepared the separate
  runner and verified its modules. Exit 0, 121.05 seconds.
- Before/after/final protected inventories match: 12744 entries, including
  7992 regular files and 3443 symlinks. Includes DOOM installation, prefix,
  installed bridge and runner, Heroic game configuration, runner records
  and stable Hub state. No game launch or live headset test.
- Targeted regressions 61/61 and 67/67 passed. Full discovery reported 1663
  tests, OK (skipped=1), 48.785 seconds. Previously skipped KHARVOX integration
  class separately passed all 11 tests using the verified fresh payload.
- Empty test HOME is not a separate OS account; complete fresh runner
  installation via automatic download tested, manual import verified at
  component level. Existing production gate stays closed.
- Evidence: /home/bananananers/NAnnersVRhub-recovery/Dev5F2A-evidence-jgPCMQ

KDE interactive acceptance pending. Dev5F3 follows acceptance.
