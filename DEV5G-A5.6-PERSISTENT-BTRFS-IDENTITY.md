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

## A5.6-D/E/F — Final acceptance
Runtime checkpoint f1e971c757a476d505e936c924155f6d89e00930.
New private Btrfs fixture: ~/NAnnersVRhub-recovery/Dev5G-A5.6-reboot-Ze0VAF.
Pre-reboot verification process 6533 passed; 11 persistent ancestor identities,
ledger schema 2, journal schema 3, five checksummed evidence files.
Actual reboot: fe004bae-6d92-4958-8731-0bc440c51ce6 to
13ca02a9-5891-4689-aeb4-570be273952c. Mount device 0:36 to 0:35.
Process 7095: persistent identity differences zero, runtime identity changed,
fresh recovery review passed, ledger/journal and 28 inventory entries unchanged.
Process 7140 reverified both fixtures and six historical manifests.
Player explicitly approved only new disposable fixture rollback.
Process 7228 reconstructed exact old review matching its original fingerprint
c166a596b85989aeec9de7ca61725ada0e3eb7b4e4256407c8b6ad9214ebd578.
Stale approval rejected; all 28 entries unchanged. Fresh review fingerprint
68e10fb30c7f58d0829113d0a6a1d50ecf387ecec44dbae486e50fc223941d1c
accepted. All 17 original entries restored byte-for-byte with modes, custom
settings and original state; retained backups verified, terminal rolled-back
journal and authority current digest verified, no pending transition.
Process 7249 independently verified final inventories and checksums.
Rollback report: post-reboot-rollback.json in new fixture directory;
SHA-256 b9871a7af00dcd5c7011893212d13d6a5ad50a040d6ca22666d185730de8c36a.
Player accepted Dev5G-A5. Final documentation checkpoint only, no runtime change.
Original failed fixture retained unmodified; stable Hub state unchanged;
all six historical manifests reverified. Production gate remains closed.
Acceptance covers normal reboot on tested Btrfs host with synthetic payloads
and isolated mocked authorization/resolvers, not sudden power loss, other
filesystems, or live installation/recovery. Next: A6 managed update/repair
requirements discovery.
