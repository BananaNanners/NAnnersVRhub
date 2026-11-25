# Dev5F2 — Player-friendly setup guides (unreleased)

Baseline: 087e16595a43386f874d2583a513f9737b59e3ca.

- Revised all nine recipes' setup, play and good-to-know sections.
- Corrected Skyrim's misplaced guide arrays under its second link entry.
- Adapted player-supplied MGO author instructions to Linux with Jackify;
  Windows-specific prerequisites are not presented as Linux requirements.
- Added 23 explicitly named guide links, separate from existing dependency
  and update sources. Both GUI and CLI guide renderers use them.
- Retained the existing layouts, launch options, version pins, hashes,
  original link metadata, installation methods and compatibility references.
  Parsed recipe comparison against baseline confirmed every non-guide field.
- Retained Cyberpunk's staged workflow, UEVR installation restrictions,
  offline-only ERVR workflow and existing backup/conflict protections.
- Removed blanket advice to delete the Ready or Not game directory.
- Six new guide tests passed, covering all nine renderings, duplicate and
  direct download links, Skyrim structure, legacy links, schema and warnings.
- Full discovery: 1661 tests reported, OK (skipped=1), 48.434 s, exit 0.
  KHARVOX standalone payload integration class remains skipped.
- Direct Nexus access was restricted during source review; MGO description
  was supplied by player. Other Nexus instructions retain existing reviewed
  scope; newer releases are not certified by this milestone. GitHub and
  other author source pages reviewed; player-facing links included in the accepted desktop guide review; direct Nexus verification remains restricted.
  .NET 6 is out of support; replacement runtime needs separate testing.
- Stable Hub state SHA256 unchanged:
  e4000197b5a4cf153e59c18058075d2a9dc312bbe2e3ff7519bae51c99370ef5.
  Production gate closed. No live install or gameplay test authorized.

Evidence: /home/bananananers/NAnnersVRhub-recovery/Dev5F2-evidence-Irrs5s

Remaining: Dev5F3 controller bindings,
Dev5G gameplay and installation acceptance, and outstanding E8 production
activation safeguards.

## Interactive KDE acceptance — November 25, 2026

Player confirmed all ten desktop setup guide checks passed: Skyrim VR,
Fatekeeper, Hogwarts Legacy, Cyberpunk 2077, Ready or Not, Subnautica,
Valheim, Elden Ring, DOOM (2016), and overall guide interface.
Accepted runtime checkpoint 4d10e8e4e2d6fd650321c7c506c794a899d74103,
preview PID 106488; previous PID 98921 closed normally. Stable state hash
unchanged and production gate closed. Development acceptance complete.
