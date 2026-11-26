# Dev5G-A5.6-B/C — Persistent Btrfs identity
Baseline ba2b192a982a941a325b1cd056aa855d3fc7a79e.
A5.5 actual reboot preserved fixture contents but changed Btrfs kernel
device numbers, causing the expected fail-closed provenance refusal.
Original failed fixture Dev5G-A5-reboot-CBnChH retained unchanged.
New production ledger schema 2 and journal schema 3 bind persistent Btrfs
filesystem UUID, subvolume UUID, subvolume ID, directory inode and paths.
Read-only FS_INFO, GET_SUBVOL_INFO and INO_LOOKUP ioctls require no sudo
on the tested CachyOS x86_64 host. Non-Btrfs identity is boot-bound.
Runtime identity additionally binds boot ID, device numbers and mount
topology; fresh approval required after reboot. Same scope retained from
approved review through recovery. Both identity layers checked in preflight.
No automatic migration of legacy evidence. Scoped development format unchanged.
Initial regression exposed two integration issues (synthetic Btrfs on tmpfs,
changed error wording); corrected tests and status reader. Targeted 82 passed
(14.687s); final 84 passed (17.738s); full 1717 passed (62.333s), process
6066 exit 0, verified KHARVOX payload included. Five added test methods
cover simulated reboot, unavailable identity, legacy authority, three
persistent identity substitutions and runtime change after review.
Original fixture 28 entries, original ledger/journal and five evidence
checksums verified; A1–A5 evidence reverified. Stable state unchanged.
No live installation, recovery, reboot, remount or GUI change. Gate closed.
Evidence: ~/NAnnersVRhub-recovery/Dev5G-A5.6-evidence-ZMISRg.
Limitations: simulated substitution and reboot, real ioctl queries on host;
actual cross-reboot recovery not yet validated. No guarantee against
malicious same-UID changes or deliberately cloned filesystem identities.
Next: independent A5.6-D versioned fixture and A5.6-E actual reboot.

Evidence manifest SHA-256: 7f48b8bcf4bd80507ed2ffe2eedce987bf59e2dc09d851d4410a6e38b084ec59.
