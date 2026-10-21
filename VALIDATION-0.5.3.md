# Release validation — October 21, 2026

- RC1 user gameplay SUCCESS recorded 13:18:34 PDT: Import bridge package,
  Test VR bridge and Launch DOOM VR worked; rendering, head tracking,
  controller input and stereo depth passed. Sampled configuration passed.
- 416 local Hub tests passed with PySide6 offscreen and the independently
  verified bridge fixture. Final metadata/version checks are repeated before
  archiving. No runtime or installer behavior changes follow the accepted RC.
- Actual published 0.5.2 updater accepted the thin candidate under its original
  limits, installed/restarted it and rolled back both ways while preserving
  fixture state/history/save bytes. Transport responses were synthetic; this
  is not a live public-endpoint update.
- The installed Hub imported the full component independently of its source
  download folder. All 94 payload files were verified. The bridge artifact is
  retained exactly as tested: SHA-256
  26dcdbef5588336954676ce2c3023f8b17c11f0263f334610d124f4a514927d0.
- Prior dev10 checks exercised actual upstream download, exact base hashes,
  empty-state runner preparation, offline reuse and owned-runner removal.

The lab 0.1.6 engine, bridge 0.2.0 source asset and binaries are unchanged.
No new game session occurred in the development container. Public bridge/Hub
publication and a real stable-endpoint update remain pending. Individual
controller mappings and other setups are not certified by the general pass.
Historical dev/rc validation documents remain unchanged for provenance.
