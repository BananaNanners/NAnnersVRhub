# NAnnersVRhub 0.5.5 — game capability matrix

All nine profiles include setup guidance, controller references, version tracking and compatibility reporting. Local evidence is not a gameplay guarantee.

| Game | Installation | Repair / update | Restoration |
|---|---|---|---|
| Cyberpunk 2077 | Existing guarded game-root installer | Review; no managed version transition | Recorded gameroot-2 originals only; legacy records blocked |
| Ready or Not | Existing PAK installer | Manual version transition | Recorded PAK backups, checksum checks |
| Subnautica | Existing exact pinned BepInEx + SubmersedVR pair | Review-only managed repair/update | Existing recorded originals, not durable transaction rollback |
| Valheim | Existing exact pinned BepInEx + VHVR pair | Review-only managed repair/update | Existing recorded originals, not durable transaction rollback |
| Fatekeeper | Dependency review and manual guidance; live pair install blocked | Recognition/review only | Live paired recovery blocked |
| Hogwarts Legacy | Dependency/profile review and manual setup; standalone CLI injector install blocked | v2.1.0 review only; configuration migration unresolved | Automatic profile and legacy injector restoration blocked |
| Elden Ring | Legacy ERVR 0.4.0 exact pin, executable 2.6.2.0 or 2.7.1.0 and existing checks required | ERVR 0.9.2 review only; INI migration unresolved | Existing recorded removal; persistent removal journal not available |
| DOOM (2016) / KHARVOX | Existing separate pinned bridge and isolated runner | Existing component guidance; newer release review | Existing component recovery guidance |
| Skyrim VR / MGO | External MO2/modlist workflow | External | External |

Supported does not mean unconditional: archive identity, destination, conflicts, ownership and backup checks depend on the installer. Use the GUI review and close the game before changes. Older CLI routes do not provide the complete GUI consent sequence. Existing legacy installers have different rollback guarantees; not all survive process interruption or power loss. ERVR version metadata is not executable authenticity verification. Application rollback switches the Hub version, not game mods or saves. Development save recovery remains opt-in and is not automatic. No new gameplay certification or new live transaction authority is granted by this release.
