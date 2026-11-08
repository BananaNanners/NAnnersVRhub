# 0.5.4 release checklist

- [x] Review save-recovery risks; fix the three reproduced findings and add regressions.
- [x] Confirm dev23 desktop rollback cancel/accept/restart with the user.
- [x] User selects GPLv3; prepare explicit GPL-3.0-only terms and preserve MIT/upstream notices.
- [x] Consolidate release notes, including installer fixes, development-only recovery features and sizing scope.
- [x] Candidate suite (598 tests), stable/dev23 managed upgrade/rollback and archive verification passed; accompanying evidence records the checks.
- [x] Candidate desktop smoke (user reported RC1 desktop pass on November 7, 2026): version, nine profiles, existing test history, recovery hidden at startup, recovery layout/blocked wording, updates rollback availability.
- [x] Review final source diff, license notice scope, release notes and checksums; unchanged RC1 behavior verified by AST comparison.
- [ ] User approves stable publication of the concrete candidate/release notes.
- [x] Promote accepted source to 0.5.4, regenerate matching version metadata, rerun required checks, build ZIP/tar.gz plus SHA256SUMS and confirm the payload matches the accepted changes.
- [ ] Publish GitHub tag/release and custom assets only after approval.
- [ ] Run actual published-endpoint in-app stable update acceptance; keep the previous managed version available.

Candidate source ZIPs are not silently offered as stable updates. App rollback does not reverse game-data or installer-schema changes. Retain and disclose the documented remaining medium findings; do not imply a zero-bug guarantee.
