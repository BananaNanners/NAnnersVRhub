# Dev5D2d — Dependency update labels and release notifications

Scope: offline UI and release metadata refinement on parent fa03bd0.
- Rename Mod Updates to Updates. Display canonical archive names for Fatekeeper and Hogwarts Legacy with distinct Mod/Profile types and existing Open source buttons.
- Fatekeeper tracks UEVR_FK.zip at the fixed available bundle release 1.0.0 and SLASHER-Win64-Shipping.zip independently.
- Hogwarts tracks HogwartsLegacy.zip against HL_UEVR and UEVR.zip against JoeyHodge independently. Profile tracking no longer combines the injector installation timestamp.
- Count confirmed update reports plus explicitly identified newer upstream release notifications, not generic review flags or errors. When the installed release identity is unknown, the upstream row remains New release — review. Never infer a verified installed version or compatibility from timestamps.
- The live checker observed Fatekeeper 1 and Hogwarts 2 notifications; latest Hogwarts profile v2.1.1 and upstream UEVR 111726DecadeofUnreal. No automatic downloads or substitutions.
- Keep previous five-column layout preferences; expanded six-column Updates preferences use a separate file. Existing source URLs and archive scan identifiers remain unchanged.
- Verification: 953 tests run, 952 passed, 1 skipped. Initial full run encountered a Qt shutdown crash; corrected new test widget disposal and reran full suite successfully with faulthandler. 187/187 isolated GUI checks passed; both rendered game pages inspected.
- Shared preview state, archive snapshots and download-folder preferences match pre-development hashes. Production, parent checkpoint, installed mods/profiles, all nine saved scans and existing live-install safety gates preserved.
- KDE desktop acceptance pending; actual updated VR gameplay and exact installed release identity remain unverified.
