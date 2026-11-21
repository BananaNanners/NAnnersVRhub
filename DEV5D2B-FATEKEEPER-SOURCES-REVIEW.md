# Dev5D2b — Fatekeeper mod/profile source separation

Parent: approved 23690d3. Branch: dev/0.5.5-fatekeeper-sources.

- Mod Updates checks Praydog UEVR Nightly and jbusfield's Fatekeeper VR profile separately.
- Upstream injector version remains Needs review until installed version identity and compatibility are established; the FK profile uses the existing profile-specific update record.
- Setup Guide labels the two requested release links explicitly; the earlier matched UEVR_FK bundle remains a separate legacy reference.
- FK v1.0.4 release instructions specify nightly 1133 and JoeyHodge backend fix. Latest upstream nightly is not automatically compatible. No automatic launcher execution, download or substitution.
- Existing archive checklist recipe identifiers, historical archive source URLs, saved scans, installer, backup/restore logic, and closed live profile replacement gate are unchanged.
- 947 tests run: 946 passed, 1 skipped. 181/181 isolated GUI checks passed. Shared preview data checksums match.
- Desktop acceptance pending; no production changes.
