# Dev5D2c — Fatekeeper packaged mod and profile sources

Goal: separate the existing packaged UEVR FK mod from the Fatekeeper VR profile, retaining the familiar setup and archive workflows. User approved the narrower proposal without additional test-status wording.

- Guide links: UEVR_FK.zip from 1.0.0, SLASHER-Win64-Shipping.zip from 1.0.0 and v1.0.4, and the profile release page.
- Install / Update uses the original two archive rows with explicit dependency labels and download links. The v1.0.4 profile link is separate. Source presentation does not alter archive scan evidence.
- Mod Updates retains the existing profile checker; the UEVR bundle reports the fixed available bundle 1.0.0. Legacy installed records lack exact release versions; do not infer an installed version.
- Standalone Nightly, separate backend fix, and one-step launcher integration are deferred.
- Production, approved 23690d3 checkpoint, parent 97cd52d, game/mod files, live-install safety gates and archive records preserved.
- Verification: 947 tests run, 946 passed, 1 skipped; 182/182 isolated GUI checks passed. Shared preview state, saved scans and folder preference hashes unchanged. Reviewed rendered Setup Guide, Install / Update and Mod Updates screenshots.
- Desktop acceptance pending. Actual game update and headset tests deferred until the improved desktop app is complete.
