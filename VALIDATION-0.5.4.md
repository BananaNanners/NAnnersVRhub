# 0.5.4 release verification

Status: final stable assets prepared for review; no GitHub publication performed.

Accepted base: 0.5.4-rc1. The user reported “Desktop check pass” on November 7, 2026 (America/Los_Angeles). Earlier explicit dev23 desktop reports confirmed rollback button/confirmation visibility, No cancellation, and Yes followed by Restart Hub. These reports do not certify fresh gameplay or every save adapter.

Changes from RC1: runtime/project version promoted to 0.5.4, updated release documentation and the optional installed validation-document inventory. Synthetic updater fixtures now use 0.5.5 as the future release and 0.5.6 for the mismatch case. Product update policy and accepted application logic are unchanged. GPL-3.0-only licensing and the MIT bridge installer notice are retained.

Final automated suite, managed upgrade/rollback evidence and archive checks are recorded in the accompanying files. User game data is not mounted here; checks use disposable fixture data. GitHub Actions and the public-endpoint stable update are not represented as passed on this unpublished revision.

Known limits, including the two deferred medium installer findings, remain disclosed in RELEASE-NOTES-0.5.4.md. Final publication approval is pending.

## Final results

- All 598 automated tests passed with PySide6 6.12.0 and offscreen Qt. The separate existing bridge fixture was used for integration tests and is not bundled.
- Managed upgrades and two-way rollback from published 0.5.3 and accepted RC1 passed. Both retained nine recipes and seven sentinel files. No game launch or bridge download occurred in these checks.
- AST comparison verified RC1 application logic is unchanged after accounting for the version label and one added validation-document filename. GPL/MIT text and bridge installer remain byte-identical to RC1; the original RC1 manifest still verifies.
- Canonical custom ZIP/tar.gz, internal source manifest and external archive SHA256SUMS are generated together. Archives retain full GPL/MIT notices and are checked against the published 0.5.3 updater's extraction rules.
- A local GitHub patch targets unchanged main at 6e7ffa0f3de3499f0e9b2f7c72335b03456bff9c; staged whitespace and patch applicability checks run before delivery. No remote commits, tags or releases were written.

This verification record describes pre-publication evidence. The actual published-endpoint 0.5.4 update check remains pending.
