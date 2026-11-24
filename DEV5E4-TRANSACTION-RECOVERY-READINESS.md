# Dev5E4 — Transaction and recovery readiness

Status: automated validation passed; interactive KDE player acceptance pending. Live Fatekeeper installation and recovery remain disabled. No release or push authorized.

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

## Player checks (pending)

1. Full Hub opens normally, existing navigation and theme intact, Fatekeeper selected.
2. Install / Update shows two ZIP dependencies and the verified backend separately, with no manual DLL copying required.
3. Existing archive scan and installation review work; exact file decisions and preservation guidance visible; live apply disabled.
4. Close the review without changes; normal navigation remains responsive.
5. Compatibility report and Updates retain independent local evidence, not inferred gameplay success.
6. Existing recovery summary remains readable; no extra player controls introduced; live recovery disabled. Pending-recovery warning is covered by automated fixtures, not injected into the working preview.
7. Hogwarts Legacy still retains its separate v2.1.0 update restriction; no live write or release promotion.

## Limitations and next gate

- Cooperative locks do not coordinate older Hub versions or external writers. Filesystem checks do not eliminate all races.
- Recovery only restores the latest transaction automatically; retained history requires manual review. Older journals without required identity/incoming state evidence require manual review. Selective recovery preserves unrelated state data, not original full-file serialization when unrelated state changed.
- The actual Qt real-payload rehearsal preceded E1; E1 has full regression coverage, but a final real-payload re-rehearsal is advisable before live authorization. No gameplay test or production mutation has occurred in this milestone.
- Live authorization remains mechanically false. Player desktop acceptance does not authorize live installation. No change to Hogwarts Legacy live update restriction.
