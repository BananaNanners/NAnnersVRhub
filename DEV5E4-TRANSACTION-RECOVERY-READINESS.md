# Dev5E4 — Transaction and recovery readiness

Status: automated validation and interactive KDE player acceptance passed (2026-11-24). Dev5E4 development milestone accepted. Live Fatekeeper installation and recovery remain disabled. No release or push authorized.

## Checkpoints and evidence

- Accepted baseline: `f175e60e96737b080e56f31a4d449112d4499862` (Dev5E3).
- Tested runtime checkpoint: `0dccca34c724e30b8b8523f4a03c5dc94248f92f` on `dev/0.5.5-fatekeeper-backend`.
- A: read-only audit reproduced process protection, repeated transaction and recovery inventory concerns.
- B1–B5: process checks at mutation boundaries, shared state transaction coordination, repeat repair with retained history, schema-2 journal and directory identity checks, completion refresh after attempted installation.
- C: official two ZIP hashes verified; actual official joeyhodge backend retrieved and verified (15,203,840 bytes, SHA-256 `b883dd7f0b5e06bff74b42b4fabc66fc7c39c6baff57634d5132abe5b05ed6fc`). Offscreen Qt worker with fixture-only commit installed 111 files and verified 108 immutable hashes; no-op, missing-backend repair, interrupted recovery, customization retention and exact pre-repair rollback passed. First harness timed out and aborted; corrected event loop completed in 2.94 seconds. No production code change was needed for that harness correction.
- D: controlled live acceptance plan; complete independent baseline backup, exact manifest, separate authorization and real gameplay checks required before any live test.
- E: 1547 tests, 1546 passed, one skipped, zero errors/failures; reproduced no-op pending-recovery bypass and unrelated state rollback refusal.
- E1: pending recovery blocks no-op and existing Install / Update action; verified incoming state retained; selective restore of Fatekeeper records preserves unrelated changes, conflicting ownership or corrupted evidence blocks recovery. Full suite: 1553 tests, 1552 passed, one skipped, zero failures/errors, 27.671 seconds, exit 0. Log `/tmp/nanners-e4e1-full.GTgxFo/results.log`. Git whitespace validation passed.

## KDE acceptance lifecycle (2026-11-24)

- Prior Dev5E3 PID 37379 absent; KWin enumeration found no Hub windows before launch; no process closed.
- Exactly one visible non-minimized development window verified by KWin: `NAnnersVRhub Dev5E4 - Transaction and Recovery Readiness`, PID 16237, started 13:57:27 local time; runtime SHA printed at launch, worktree verified through proc cwd. Launch serialized with preview-specific flock.
- Existing full Hub launcher, title-only subclass, Fatekeeper selected on Install / Update; persistent isolated preview state `/home/bananananers/.local/share/nannersvrhub-development-preview/state.json`. Stable state SHA-256 unchanged before and after launch: `e4000197b5a4cf153e59c18058075d2a9dc312bbe2e3ff7519bae51c99370ef5`.
- Verified startup: pinned backend already installed, two ZIP roles, live gate false. Window left open for player acceptance.

## Player checks (accepted 2026-11-24)

Player explicitly reported all seven Dev5E4 desktop acceptance checks passed. The following records the actual checklist presented for acceptance, not a new gameplay test or live-write approval.

1. PASS — Full Hub opens normally and existing navigation works.
2. PASS — Install / Update displays exactly two ZIP dependencies.
3. PASS — UEVRBackend.dll shows Verified pinned build installed.
4. PASS — Archive scanning and Review installation work correctly.
5. PASS — Installation review displays file decisions and keeps live installation disabled.
6. PASS — Compatibility and Updates display the correct dependency evidence.
7. PASS — Existing recovery information is readable, with no unnecessary new controls.

At acceptance PID 16237 remained running and stable state SHA-256 still matched the launch baseline. The prior documentation checkpoint was `b5c0be463291f75e2ec83341bded47440c97c1a5`; runtime checkpoint remains unchanged. Pending recovery is covered by automated fixtures, not injected into the working preview. Hogwarts Legacy remains separately gated; the desktop checklist did not constitute new Hogwarts gameplay or update validation.

## Limitations and next gate

- Cooperative locks do not coordinate older Hub versions or external writers. Filesystem checks do not eliminate all races.
- Recovery only restores the latest transaction automatically; retained history requires manual review. Older journals without required identity/incoming state evidence require manual review. Selective recovery preserves unrelated state data, not original full-file serialization when unrelated state changed.
- The actual Qt real-payload rehearsal preceded E1; E1 has full regression coverage, but a final real-payload re-rehearsal is advisable before live authorization. No gameplay test or production mutation has occurred in this milestone.
- Live authorization remains mechanically false. Player desktop acceptance does not authorize live installation. No change to Hogwarts Legacy live update restriction.
