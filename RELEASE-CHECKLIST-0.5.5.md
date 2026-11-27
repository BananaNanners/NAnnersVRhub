# 0.5.5 final release checklist

## Candidate preparation
- [x] A6.6-A/B distribution and managed resources audited.
- [x] A6.6-C/C1 production entry points audited and legacy safety corrections sealed.
- [x] A6.6-D/D1 real stable-to-candidate upgrade and two-way rollback rehearsed with simulated release delivery.
- [x] Version declarations promoted; player-facing notes and capability matrix prepared.
- [x] Verify final candidate archive hashes, exact tracked source inventory, managed resources and real installation/upgrade/rollback with accepted candidate assets (5950f47).
- [x] Full versioned candidate regression, normal exit and lifecycle logs.
- [x] Reaudit historical evidence, stable state and closed production gates.

## KDE player acceptance (isolated read-only candidate)
- [x] Identify previous preview; safely close it or verify absent; exactly one current preview.
- [x] Verify Git checkpoint, loaded runtime and process; stable Hub unchanged; leave candidate open.
- [x] Version 0.5.5, responsive navigation and all nine game profiles.
- [x] VR System scan, WiVRn/headset status, auto-refresh and copy report.
- [x] Archive scan persistence, human-readable sizes, verified/missing/review statuses and context-aware actions.
- [x] Setup guides and controller references for all nine games.
- [x] Restricted Fatekeeper/Hogwarts actions, ERVR review and BepInEx maintenance guidance; no live writes.
- [x] Compatibility/history and logs distinguish current checks from prior gameplay.
- [x] Hub updates displays candidate version and correct managed/source-run limits; no public update or install in preview.
- [x] Development tools hidden by default; existing controls and layout retained.
- [x] User explicitly accepts candidate and notes any observations.

## Publication (separate authorization)
- [ ] Verify documentation-only publication archives against accepted application code and repeat managed installation/upgrade/rollback.
- [ ] User approves exact candidate, release notes, scope and asset checksums.
- [ ] Push/tag/publish only after explicit approval.
- [ ] Actual published endpoint update acceptance in approved environment; retain previous managed release.

No approval of publication or new live game transactions is implied by any checklist item.
