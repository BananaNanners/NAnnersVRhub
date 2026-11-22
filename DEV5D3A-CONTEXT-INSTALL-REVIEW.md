# Dev5D3-A — Context-aware installation actions

Approved scope: offline UI routing from 9775d0c, no live installation authority.
- Selected UEVR profile archive goes directly to the existing profile review planner/dialog; injector rows and guide-only games open Setup Guide. Manual profile picker uses the same reviewed path. Profile dialog is read-only and no acceptance result can invoke writes.
- Generic mod review and complete pinned archive batch remain on the existing manifest and consent/revalidation route. No new installer or source substitution.
- Recheck current folder, recipe identity and saved archive file identity at click time. Refuse changed/mismatched/unverified archive selection or incomplete pinned sets; do not silently replace them with a picker. Manual selection remains available, subject to the existing review engine.
- Game changes clear previous row selection. Request dispatcher rejects mismatched game IDs and unsupported profile routes.
- 62 focused tests passed. Full regression: 961 run, 960 passed, 1 skipped. 202/202 isolated GUI checks passed, including actual widget navigation and mocked routing for both UEVR games. Rendered Fatekeeper and Hogwarts profile action screenshots inspected. No actual VR gameplay or new live installer capability verified.
- State, nine archive scans and download-folder preferences match original SHA-256 checksums. Production, parent worktree, installed game/mod/profile data and live safety gates preserved. Desktop acceptance required.
- Dev5D3-B dependency guidance and Dev5D3-C interface cleanup deferred.
