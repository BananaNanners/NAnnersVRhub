# Dev5G-A6.7 — Cross-game workflow consistency
Approved roadmap: A permanent host XDG discovery correction; B capability
inventory for all games; C shared maintenance presentation; D BepInEx
maintenance safety requirements; E cross-game desktop regression.
Equivalent capabilities should share controls, terminology and protections.
Unsupported operations must not be advertised. Game-specific validation
remains mandatory. A6.6 final maintenance readiness is still pending.

## A6.7-A
Baseline f452791ec76f4b6cb2f0563cc9c1628246207734.
Read-only audit reproduced native Heroic discovery failure after preview
XDG isolation. Central preview activation now captures host XDG before
redirecting paths; capture is idempotent. No game-specific fallback.
Disposable regression covers three repeated activations, explicit legacy
capture calls, Heroic game/prefix/profile, OpenXR and child environment.
Targeted suite 46 passed (0.357s), process 25064 completed.
Actual host discovery succeeded for all three activations in one process.
Stable state unchanged; gate closed. A6.5-D sealed evidence reverified.
Fresh independent process restarts and KDE acceptance remain pending.
Evidence: ~/NAnnersVRhub-recovery/Dev5G-A6.7A-evidence-FeHRcM.

Manifest SHA-256: 87b047dd28c4f37606d3c6698fed47b31a9a1592dca6cda23a046a51a8c37a07.
