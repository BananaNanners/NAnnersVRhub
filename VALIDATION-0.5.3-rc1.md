# Release candidate validation — October 21, 2026

- 416 Hub tests passed with PySide6 offscreen and the independently verified
  bridge payload supplied as a test fixture.
- 14 new component checks cover pinned archive transport/import, no network
  on probe, corruption/truncation/limit rejection, atomic activation, locking,
  cache reuse, source boundaries and runner metadata preservation.
- Actual finalized companion archive imported into an empty component state;
  all 94 engine/source/binary payload files verified before import.
- Actual published 0.5.2 source ZIP was downloaded and its published SHA-256
  verified. Its original updater/installer (32 MiB archive / 8 MiB file caps)
  accepted a synthetic 0.5.3-labeled candidate, installed it, restarted it,
  loaded all nine recipes without the bridge, and rolled back both ways.
  Fixture state, test history and an external save sentinel were preserved.
- Prior dev10 checks: actual upstream base download, seven baseline digest
  comparison, empty-state clone, offline runner reuse and owned-runner removal.
  User subsequently reported the dev10 on-PC Install/Test/Launch check passed.

The candidate changes distribution only; the lab 0.1.6 engine and binaries are
unchanged. It requires a user import/launch check before final 0.5.3 labeling.
No new Wine/headset/game session occurred in the development container.
Bridge repository, asset publishing and public-endpoint update remain pending.
Historical dev8/dev9/dev10 docs are retained for provenance; current instructions
are README.md and UPDATE-TESTING-0.5.3-rc1.md.
