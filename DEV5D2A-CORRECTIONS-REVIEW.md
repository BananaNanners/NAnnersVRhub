# Dev5D2a — user desktop review corrections

Parent: 397c5a3. Isolated branch dev/0.5.5-archive-first-fix. No released files changed.

- Archive and profile review acknowledgements are available from the default collapsed view. Inventories are optional disclosures. Acknowledgements accurately refer to the summary, destination and backup policy, and are not reset on disclosure.
- Both reviews show selected archive, dependency and review evidence. For multi-package pinned plans match the exact reviewed SHA-256 to the recipe; for game-root plans match the validated component identifier. Never assume selection order. Profile review shows Matching game profile.
- Hogwarts Legacy retains its independently tested matching HL_UEVR bundle and profile sources. Add the user-specified JoeyHodge release reference to Setup Guide and Install / Update. The selected tag 100526UE58_6RefreshUpdate contains DLL assets rather than a complete ZIP; do not substitute it automatically.
- Add independent upstream UEVR release checking through the existing GitHub release client. The latest release tag is displayed in Needs review: the installed upstream release identity is unknown. Do not compare the downstream bundle's installation time with upstream release dates.
- Existing backend manifest, backup, conflict, revalidation, production and live UEVR execution gates remain unchanged. All acknowledgements still required for supported live installs; all actual installation operations remain disabled in the preview.
- Full regression: 943 run, 942 passed, 1 skipped. After final profile layout correction: 17 focused checks and 177/177 isolated GUI checks pass. Visual summary screenshots reviewed. Shared preview scan/state/preferences hashes unchanged.
- User desktop acceptance pending.
