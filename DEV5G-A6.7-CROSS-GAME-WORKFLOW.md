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

## A6.7-A final acceptance
Three independent fresh processes (25566, 25567, 25568) resolved the actual
Hogwarts game and Heroic prefix after preview isolation. Host XDG and
Heroic metadata remained unchanged. Player confirmed all nine cross-game KDE
checks passed on isolated preview PID 25571, runtime checkpoint
0c4a07874aa20b53c748c8c432801d3aeef16577. Qt-visible 1630 x 1060;
independent compositor inspection not established. SteamVR selected runtime,
not proof of running service. Previous preview PID 20755 absent before launch.
Stable Hub state unchanged, production gate closed. Original manifest retained.

Acceptance manifest SHA-256: 3aa54c7d5eafc11d1a2f6445b552e9986d971cacdda2064641e4a2624df48c52.

## A6.7-B — Shared capability inventory and preview policy

Baseline a9d8d5ed5738871c906d5db069f1af9d2b935ac5.
The immutable capability inventory describes existing routes, not permission,
readiness, ownership, upstream compatibility or gameplay. Unknown games default
to unsupported. It does not yet drive shared maintenance presentation (C).

I = implemented; R = restricted; N = unsupported; E = externally managed.
An implemented route still requires its existing handler guards.

| Game | version_check | install_review | install | integrity | recognition | repair | update | original_restore | latest_rollback | persistent_recovery |
|---|---|---|---|---|---|---|---|---|---|---|
| fatekeeper | I | I | R | I | I | R | R | N | R | R |
| hogwarts-legacy | I | I | R | R | N | N | R | R | N | N |
| subnautica | I | I | I | I | R | N | N | I | N | N |
| valheim | I | I | I | I | R | N | N | I | N | N |
| elden-ring | I | I | R | I | R | N | N | I | N | N |
| ready-or-not | I | I | I | R | N | N | N | I | N | N |
| cyberpunk-2077 | I | I | I | I | R | N | N | I | N | N |
| doom-2016-gog | I | R | R | R | R | N | N | R | N | N |
| skyrim-vr-mgo | I | E | E | R | R | E | E | E | E | E |

The shared ReadOnlyPreview preserves ordinary availability checks, permits manual
update refresh, source links, archive scan/inspection, install review, integrity
and compatibility checks, and isolated archive-folder preferences. It disables
transfers, installation, removal, rollback, mark-current, Nexus credential edits,
game launch dispatcher, development tools and Hub application update. Preview
startup omits automatic updates/setup scans; manual update worker skips Nexus
name-cache writes. Ordinary Hub startup and update worker defaults are unchanged.
Policy is UI review protection, not a backend security boundary or a general
read-only filesystem sandbox. Preview preferences/scan results may be persisted
in isolated storage. No new production authorization or game recipe changes.

### Validation

Initial dedicated 3 passed (0.697s); targeted 124 passed (7.838s).
Final dedicated 4 passed (1.100s, process 27405), including blocked duplicate
refresh and navigation through all nine games during a held update worker,
simulated scan completion, restrictions after refresh, and suppressed metadata
writes. Network results and scan completion are mocked in this asynchronous test.
Full unittest discovery: 1755 passed (77.560s, process 27588, exit 0),
no failures/errors/skips; 11 KHARVOX BridgeTests included using a private copy
verified against the pinned manifest and package inventory. Offscreen Qt and
isolated state/config/cache/data; not a new live gameplay test.
Earlier actual read-only lookup recorded all nine recipes and unchanged stable
and isolated state. Subnautica and Valheim current, Hogwarts one update and one
unknown, Fatekeeper pinned backend verified and two unknown, DOOM unknown,
Cyberpunk and Ready or Not no Nexus key, Elden Ring and Skyrim no update rows.
Authenticated Nexus lookup remains unverified; unknown versions are not current.

### Preservation and acceptance gate

20 prior Dev5G manifests checked against committed hashes; 83 entries verified.
Both A5 fixture inventories (28 entries each) and original checksum sets matched;
A5.6 rollback report matched committed digest. Exact regular-file membership,
hashes and modes of 11 injector and 110 Fatekeeper profile files matched E8.
Stable state matched A6.7-B baseline before/after regression:
8ee962ac73ca851b5efb6d3091eafd5bfe5289f638af38739344ec474dd7fb90.
Older E8 state differs due to documented F3 metadata refresh; no claim of
unchanged state since E8. Not a comprehensive audit of all game files, saves,
prefixes or symlinks. Production gate independently checked closed.
Existing A6.7-A preview PID 25571 retained; running checkpoint 0c4a078,
not the new B code. Interactive KDE acceptance remains pending; replace safely
per AGENTS.md only after verifying process/window and idle state. No release,
push, live install or recovery. A6.7-C/D/E and A6.6 readiness remain pending.

Evidence: ~/NAnnersVRhub-recovery/Dev5G-A6.7B-evidence-MbSbDx.
Manifest SHA-256: 789b490c51999ec77dbea8a10b64fa4c825edc3eb5832725ab25c0f542628ffa.

## A6.7-B — Nexus preview correction and player acceptance

Player accepted ten original KDE checks (PID 29005) and four authenticated
Nexus checks (PID 29718), both at runtime b498ed068ff30a96553033d984b7319f9e0af513.
The original launcher omitted the existing read-only credential fallback;
corrected launcher proved the workflow before permanent centralization.
Shared desktop activation now uses captured host XDG configuration for the
read-only default host key and explicitly isolates the writable key path.
No credential copy, disclosure, or change; existing fallback validates regular
private user-owned source and rejects symlinks. Missing key is not fatal.
Custom host XDG, repeated activation, isolated write/delete and insecure/missing
source regression added. Explicit host key-file overrides are not inherited
as writable preview targets; environment API key precedence is unchanged.

Targeted 30 passed (1.254s, PID 30422); authenticated live check PID 30454
exit 0 (4.19s): Cyberpunk 15 rows (6 update, 7 current, 1 not installed,
1 unknown); Ready or Not 1 current. Credential bytes/mode/mtime and both
state files unchanged during live check. Full regression 1757 passed
(77.799s, PID 30517, exit 0), no errors/failures/skips, verified private
KHARVOX payload included (11 integration tests).
21 previous manifests/92 entries, both reboot fixtures (28 entries each),
121 Fatekeeper regular-file members/hashes/modes and stable state verified.
No comprehensive all-game/save/prefix audit. Production gate closed.
Previous preview PID 29718 absent. Fresh KDE verification and player
confirmation of permanent source correction remain separate from 14 prior
accepted checks. No push, release, live installation or recovery.

Evidence: ~/NAnnersVRhub-recovery/Dev5G-A6.7B-nexus-final-hobDWm.
Manifest SHA-256: 0c3ad2528f857361e4e0dfd5625cd2cdbe00250dcf9196a749dde7710ef80dc9.

## A6.7-B2 — Permanent development preview launcher

Baseline 5178e3774aa175e6d3224940d33c4adafc33eab1.
Explicit entry point: `python3 -B -m vrhub.dev_preview` from the clean
development worktree. Refuses dirty trees and open production gate.
Reuses shared read-only UI policy, isolated storage and private Nexus
fallback; logs PID, checkpoint and state path. Normal Qt close handlers
unchanged. Shared activation acquires a nonblocking Linux advisory lock
before storage migration, held until process exit. Repeated activation
in the same process is supported. Older launchers using current shared
activation participate; historical source copies or nonparticipating
launchers are not covered. Continue manual window/process identification
per AGENTS.md; no forced close. No production authorization change.

Targeted 20 passed (0.157s, process 35385). Full regression 1761 passed
(77.859s, process 37229, exit 0), no failures/errors/skips, isolated
Qt/XDG/state and private KHARVOX payload copy. Cross-process contention,
lock reuse, legacy activation refusal before migration, open gate and
dirty tree refusal tested. No new GUI startup acceptance implied.

22 historical manifests / 104 entries verified against baseline docs.
Both reboot fixtures matched 28 entries each and original checksums;
A5.6 rollback report matched committed digest. E8 protected injector
(11 files) and profile (110 files) matched membership, hashes and modes.
Initial preservation script erroneously treated the E8 stable state file
as a directory; recorded partial log retained. Independent follow-up
confirmed stable state checksum matches current approved A6.7-B baseline
and pre-regression checksum, not E8 (documented F3 metadata refresh).
Production gate closed. No exhaustive all-game/save/prefix audit.

KDE checklist: previous preview absence reported by player earlier;
recheck before launch. Current window/PID/checkpoint, exactly one
preview, stable Hub preservation during launch, normal close/relaunch,
Nexus refresh and player acceptance remain pending. No live install,
push or release. A6.7-C/D/E and A6.6 remain pending.

Evidence: ~/NAnnersVRhub-recovery/Dev5G-A6.7B2-regression-2fK3JJ.
Manifest SHA-256: 4a9d883d2f4e876dc65c3982d1f8525ef828711c7489eb4d59432018eb4d01bc.

### A6.7-B2 player acceptance record
All ten desktop checks explicitly passed by player. Subsequent independent
inspection found no matching preview process or held lifecycle lock.
Running checkpoint/PID, compositor window and left-open verification remain
pending; do not represent player confirmation as independent observation.
Stable state unchanged, gate closed. Original regression manifest retained.
Acceptance manifest SHA-256: 06cdd533782bdd91a911c00bbe07baab24a4a26a184c26a82be8e7232fbd0e65.

## A6.7-C — Shared maintenance presentation
Baseline 389d4f62dc0a05452957c72753fb5399c91d9c1c.
Capability inventory drives existing restoration controls and Updates explanation.
Fatekeeper latest rollback, Hogwarts original profile, five generic removal/
restoration routes, KHARVOX guidance and external Skyrim maintenance remain distinct.
No new controls, handler changes, or authorization. Existing install/repair review
labels and version detection retained. Nine-game normal/preview switching and
unknown capability tests passed; targeted regression 72 passed.
Two full suites reported 1764 passing assertions but exited 139 during native
Qt/PySide cleanup. Focused reproduction exited 0, 139, 134. Explicit close,
deleteLater and deferred-delete processing added only to new test widgets.
Five subsequent focused runs (28 tests each) exited 0; full corrected regression
1764 passed (74.645s), process 44065 exit 0. Exact defective object not proven.
Both failed logs retained and hashed. Source hashes captured at sealing.
24 historical manifests / 110 entries, two 28-entry reboot fixtures, 11 injector
and 110 profile files reverified; stable state unchanged; production gate closed.
Audit covers recorded protected inventory, not every game file or save.
Interactive KDE acceptance pending; no preview launched by this step.
Evidence: ~/NAnnersVRhub-recovery/Dev5G-A6.7C-corrected-tsPKzB.
Manifest SHA-256: ce6a850788b9123e2a7785a4a1de55737e75ed0d07818e0b82316b0efe13ef80.

### A6.7-C player acceptance
All twelve KDE checks passed by player. Runtime checkpoint 6564c7f07953eeeab43914c9aa1fcf397fd86616; PID 45512,
start 2026-11-25 23:42:34 PST, launcher output and isolated state supplied
by player; independently observed process/worktree/held lock. Preview remains
running. Independent compositor identity and previous window absence remain
unverified. Stable state unchanged; gate closed. Original manifest retained.
Acceptance manifest SHA-256: a74be18042683fca5cd4f915eb8b2a44fdfd5c71c8afdf45c300f0ba78ab4f24.

## A6.7-D1 — BepInEx dependency recognition
Approved D1–D5 scope; baseline c60a9434e7895eaad450c349bc3d4b4924c7536a.
Subnautica and Valheim only: complete pinned pair, current byte comparison,
missing/different/modified-settings classifications, known conflicts, repeated
sampling, unsafe targets rejected. No ownership, compatibility, gameplay or
write authorization. Settings classification by extension is provisional.
Existing Verify installed files control reused; historical integrity separate,
no new controls or maintenance routing. Evidence cleared on selection/rescan.
Cancellation discards results after sampling; per-file interruption not implemented.
Disposable fixtures 66 passed including Elden Ring. Initial GUI 65/67 passed;
two worker timeouts. Trace showed filesystem work; corrected configured Steam
root discovery in recognition and historical package integrity, and test event
wait. Contributions not independently isolated. Four focused runs 6/6 each,
expanded targeted 116/116. Full 1787/1787 in 73.546s, unittest exit 0, no crash.
Shell exit 1 from separate audit syntax error; corrected audit exit 0.
Five source hashes verified before/after. 26 manifests, 122 entries, both
28-entry reboot fixtures, 11 injector and 110 profile files preserved; stable
state unchanged; production gate closed. Audit not a whole-game/save inventory.
Evidence: ~/NAnnersVRhub-recovery/Dev5G-A6.7D1-full-lodLGh.
Manifest SHA-256: b3e1043e7de5dbe05c3213059468d28e4884b32c1b3f5e5895516b38b83a4f75.
Earlier failed evidence referenced by checksum. Interactive KDE acceptance
pending; no preview replacement performed by sealing.

## D1 player acceptance seal
Player reported 12/12 KDE checks passed at runtime c91fd63b64312e0296c6221d7b4cbbc672df34ab, previous PID 49534. Independent compositor identification not established.
Combined D1/ERVR acceptance evidence: ~/NAnnersVRhub-recovery/Dev5G-A6.7D1-ERVR-acceptance-GsacgW.
Acceptance manifest SHA-256: 1bb65584ad87977ea12efa987e928f000336cc637965dc6abe29a0d61f4b1d18.
27 historical manifests/132 entries, 20 ERVR entries, nested D1 evidence, both reboot fixtures and 121 Fatekeeper files verified. Stable state unchanged, gate closed.

## D2-A — Read-only repair evidence
Baseline 2d7489b981d1f2f827b34544d52115cd16137fff. Bounded ZIP snapshots bind pin hashing and member inspection to the same bytes; installed-file reads reuse descriptor-based integrity checks with before/after identities. Exact package/global inventories and hashes classify record consistency, not ownership authority. Configuration and binding paths receive conservative protection. Recorded originals checked against hashes; retired legacy trees lack trusted inventory and remain unverified. Production archive caller retains its existing behavior; no repair dispatch, pin change, or GUI change.
Twelve additional tests, targeted 64/64, full 1824/1824 (80.885s), process 60685 exit 0. Three changed source/test hashes and stable state matched after regression. Preservation audit: 28 historical manifests/135 entries, ERVR 20 entries, nested D1, two reboot fixtures and 121 Fatekeeper files. Gate closed.
Evidence: ~/NAnnersVRhub-recovery/Dev5G-A6.7D2A-full-QrolJq.
Manifest SHA-256: 1f7034bbeecceb0b880e8a3a200fbb009ed7d3fdf42fcd8e7aa2d6781c999dfc.
Limitations: sampling cannot certify absence of concurrent changes; ancestor path reads and legacy backup provenance are not transaction authority; retired trees unverified. Backup validation is recorded-original evidence, not a complete backup inventory. D2-B exact repair manifest, D2-C UI, D2-D desktop acceptance pending. ERVR preview retained at runtime 3e9b2b1, not this new code.

## D2-B — Exact read-only repair manifest
Baseline 9cdbd7e2d2a229371c65b827d66fed95577137ff. Deterministic per-pinned-file review with sampled/expected hashes, component, action and reason. Preserve matching files and existing protected settings/bindings; missing protected files require manual review. Proposed restore/replacement only with consistent recorded inventory, matching recorded original backups and no known conflicts or missing protected settings. All such proposals suppressed when blockers exist. Unknown evidence returns no partial inventory. Outside-package files excluded, not comprehensively inventoried. No repair dispatch, GUI changes, pin promotion or write authority.
Eleven new tests; targeted 75/75, full 1835/1835 (83.824s), process 61548 exit 0. Both new source/test hashes and stable state matched after regression. Corrected preservation audit: 29 historical manifests/141 entries, ERVR 20 entries, nested D1, two reboot fixtures, 121 Fatekeeper files. Initial audit invocation failed with Python syntax error; empty output and failure note retained; corrected audit passed. Gate closed.
Evidence: ~/NAnnersVRhub-recovery/Dev5G-A6.7D2B-full-RYMiXX.
Manifest SHA-256: 1b882f9f8faaa9836d0a143f1018993d68da9f1ec219643a6c61aacad8b3ee1a.
Limitations: D2-A sampling and backup provenance restrictions remain. Review is not execution authority, compatibility evidence or a complete backup inventory. D2-C interface integration and D2-D desktop acceptance pending. No preview replacement, push or release.

## D2-C — Existing Install / Update repair review
Baseline b0be460bb2c905342a0e4fa829770ebbcd32cbd9. Existing Verify installed files worker derives read-only repair review from the same recognition sample; existing summary and details panel display counts, blockers, complete pinned inventory, proposed actions, reasons and hashes. No new controls, execution route, branding changes or pin promotion. Game switching and cancellation suppress stale results. Initial full regression 1839 tests, one failure (empty review unnecessarily expanded details); exit 1. Corrected presentation keeps empty-review blockers in summary and retains historical details behavior. Existing assertion unchanged.
Corrected targeted 87/87; full 1839/1839 (81.447s), process 63027 exit 0. Three source/test hashes and stable state matched. Preservation audit: 30 historical manifests/149 entries, ERVR 20 entries, nested D1, two reboot fixtures, 121 Fatekeeper files. Gate closed.
Original evidence: ~/NAnnersVRhub-recovery/Dev5G-A6.7D2C-full-yu6ib1.
Combined evidence: ~/NAnnersVRhub-recovery/Dev5G-A6.7D2C-corrected-Ts6f6j.
Manifest SHA-256: c4ad9b2cd3a97a3da1cd9b2dd7485f79968d48d3b99526be02cfdd8fca402e51.
Limitations: offscreen GUI tests only; interactive KDE readability and acceptance pending D2-D. Read-only review is not repair authority; sampling and legacy backup provenance restrictions remain. No preview replacement, push or release.

## D2-D — Player desktop acceptance
Player reported 14/14 interactive KDE checks passed at runtime e0c9aa045d398438b3cac865b1b6f86823b5e80d, PID 66532. Independent compositor identification not established. 31 historical manifests/160 entries verified; stable state unchanged; gate closed. Evidence: /home/bananananers/NAnnersVRhub-recovery/Dev5G-A6.7D2D-acceptance-YbMNu9.
Manifest SHA-256: a240a561fc07fd06a9ca024e9cff3122eabdd3df988c512d6e4b3d78a32fafc2.
D3 backup and transaction development pending.

## D3-A — Synthetic repair backup and transaction adapter
Baseline faffb1d8b2fc0601aac10318a8168f585b721d98. Fixture-only Subnautica/Valheim adapter uses existing offline transaction engine with synthetic recognition evidence and simplified historical record distinct from the complete present-fixture snapshot inventory. Changed binary replaced, missing binary restored; protected settings, bindings, unrelated mod/save sentinels, historical backup and record preserved. Verified pre-apply backup and explicit rollback restore fixture bytes, modes and topology including prior absence. Stale current/incoming bytes rejected. No production dispatch or caller-supplied destination paths.
Seven new tests; targeted 47/47; full 1846/1846 (81.687s), process 71490 exit 0. Two source/test hashes and stable state matched after regression. Historical audit: 32 manifests/163 entries, ERVR 20 entries, nested D1, two reboot fixtures, 121 Fatekeeper files. Gate closed.
Evidence: ~/NAnnersVRhub-recovery/Dev5G-A6.7D3A-full-5vQe9X.
Manifest SHA-256: cb2b8487e1aa83b08ce9b8fa1a9d00c06c8529ae70801521eabc3ed28a73404a.
Limitations: synthetic package subset and manually constructed recognition evidence, simplified ownership record, not complete real archive or production schema validation. Engine inventory represents fixture snapshot coverage, not real ownership. Comprehensive interruption, persistent recovery, and actual schema validation remain pending. No desktop replacement, live writes, push or release.

## D3-B — Independent-process interruption and persistent recovery
Baseline 6641f72d8cc30e30330c5f21f723392d3c3a76ce. Eight new tests across Subnautica and Valheim synthetic repair fixtures exercise process exit during preparation, backup, staging, replacement, inventory publication, rollback and directory cleanup; independent recovery and repeated recovery restore prior snapshots and inventory. Unexpected changes to binaries, settings, saves, historical records, original backups, fresh backups and malformed journals block recovery without installed-file changes. Committed transactions require explicit rollback. No transaction engine or production dispatch changes.
Initial targeted run had two malformed-journal assertion failures: engine correctly refused invalid JSON with TransactionBlocked rather than RecoveryBlocked. Harness now distinguishes both refusal types; original log retained byte-for-byte. Corrected targeted 55/55 (3.972s); full 1854/1854 (84.195s), process 72177 exit 0. Source hash and stable state matched. Historical preservation: 33 manifests/169 entries, ERVR 20 entries, nested D1, two reboot fixtures, 121 Fatekeeper files. Gate closed.
Evidence: ~/NAnnersVRhub-recovery/Dev5G-A6.7D3B-corrected-zaQaJf.
Manifest SHA-256: 48c1941222e501ce48435feccda82c07bf2ccc665f9e1ed2928e5e45730947b2.
Limitations: synthetic fixtures and injected process exits, not physical power-loss/reboot certification. Full real archive and production ownership schema validation remain pending. No desktop replacement, live writes, push or release.

## D3-C — Complete pinned archive repair and rollback rehearsal
Baseline 2b446b706c9c4bf4fe44b2166ba8f5ccc3dd9eca. Four original ZIPs and four retained copies match existing recipe SHA-256 pins. Complete mapped payloads (Subnautica 45, Valheim 135 files) use shared archive mapping, actual recognition and review, and schema-accurate disposable Hub records. Existing larger bounded fixture mode reused without engine changes. Verified backups cover 49 and 139 present fixture files respectively; two proposed repair actions per game, custom settings/bindings, unrelated sentinels, historical originals and state preserved; byte/mode/topology rollback and inconsistent record rejection verified.
Four new tests; initial 4/4, expanded targeted 59/59 (4.908s), full 1858/1858 (84.422s), process 73093 exit 0. Two source/test hashes, stable state, eight archive hashes verified. Historical preservation: 34 manifests/176 entries, ERVR 20 entries, nested D1, two reboot fixtures, 121 Fatekeeper files. Gate closed.
Evidence: ~/NAnnersVRhub-recovery/Dev5G-A6.7D3C-full-8Nl3LY.
Manifest SHA-256: 4106c6743001ee1686faeffb357659c79e2f58903e1df8e9802e5fd53ae87f32.
Limitations: actual pinned archive bytes, but synthetic game layout, customizations, original backups and schema-accurate records. Recognition discovery/state location patched only for fixture; no production installer invocation. Historical ownership record remains unchanged, engine inventory is fixture snapshot coverage, not production authority. D3-B process interruption matrix uses smaller synthetic fixtures, not these full inventories; no physical power-loss certification. No GUI change, live write, push or release.

## D3-D — Combined pinned inventory interruption and recovery acceptance
Baseline 4226d4ca667623fa32cd00818ab28ea8da3410b7. Reused D3-B independent-process interruption harness with D3-C complete pinned inventories and schema-accurate disposable ownership records. Subnautica 45 pinned/49 backup files; Valheim 135 pinned/139 backup files. First/middle/final backup interruption, staging, replacement, inventory publication, interrupted rollback, tamper rejection, explicit rollback, full backup hashes and post-recovery recognition verified.
Initial 18-test run had two failures because full inventories already contain BepInEx/core and therefore create no new directories. Corrected harness explicitly checks planned directories; small fixtures retain actual cleanup interruption coverage, full fixtures verify existing directories are preserved and cleanup fault does not fire. Original failed log retained byte-for-byte. No transaction engine changes.
Corrected targeted 20/20 (16.791s); full 1870/1870 (97.294s), process 74377 exit 0. Two test source hashes, four pinned archive copies and stable state verified. Historical audit: 35 manifests/189 entries, ERVR 20 entries, nested D1, two reboot fixtures, 121 Fatekeeper files. Gate closed.
Evidence: ~/NAnnersVRhub-recovery/Dev5G-A6.7D3D-corrected-cg0HWj.
Manifest SHA-256: 3ad8f2b448c7b44bb41ec45f1457e3ac99e7c1e05dfd8880d2c1ecaabeca3559.
D3 fixture validation complete. Limitations: injected process exits, not physical power-loss certification; schema-accurate synthetic records and disposable destinations, not live production repair authorization. No GUI change, live writes, push or release. D4 managed updates remain pending.

## D4-A — Read-only managed update foundation
Baseline ac8f1b813c8b49663040088465434106955806ff. Added scoped Subnautica/Valheim review model using existing release catalogs, download planner, archive comparison and installed provenance. Separates recorded installed identity, recipe pin and candidate identity; candidate bytes are rehashed using bounded immutable archive snapshots. No candidate approval or pin substitution. Thunderstore loader remains manual review.
Four new fixture tests; initial targeted 41/41 (0.272s), repeated targeted 41/41 (0.273s), full 1874/1874 (100.168s), process 76126 exit 0. Source/test hashes, stable state and both recipe hashes verified. Historical audit: 36 manifests/197 entries, ERVR 20 entries, nested D1, two reboot fixtures, 121 Fatekeeper files; all recipe TOMLs unchanged. Gate closed.
Evidence: ~/NAnnersVRhub-recovery/Dev5G-A6.7D4A-full-WuBPSR.
Manifest SHA-256: d89a64fc9e9eb42cbb8ee5fa72307a746e23d816220d68afb9eb3956b377c725.
Limitations: simulated release metadata and candidate bytes, not actual newer upstream ZIPs; identity alone does not validate archive contents or compatibility. Installed provenance is historical, not current-byte verification. Thunderstore automated discovery, exact manifests, transaction integration and GUI integration remain pending. No production writes, pin changes, GUI changes, push or release.

## D4-B — Exact read-only managed update manifests
Baseline 880437c6de90e6435a9cf71b54e21730637613d6. Complete synthetic baseline/candidate pairs mapped through existing archive mapper using a private mapping-only recipe copy. Fresh recognition supplies current bytes, historical ownership and backup evidence. Install/Replace/Preserve/Remove/Block rows include component, path, reason and old/current/new hashes. Both games test classifications, custom settings, unowned destination, changed binary, inconsistent ownership and tampered candidate refusal. No write or compatibility authorization.
Initial targeted 2/2 (0.089s), expanded targeted 83/83 (0.957s), full 1876/1876 (97.326s), process 77217 exit 0. Historical audit 37 manifests/205 entries, ERVR 20, nested D1, two reboot fixtures, 121 Fatekeeper files; all recipe TOMLs unchanged. Stable state unchanged, gate closed.
Evidence: ~/NAnnersVRhub-recovery/Dev5G-A6.7D4B-full-LQe5HF.
Manifest SHA-256: 8a4fcad6c3df0c5426b7fdaee50fd81fca3f7747076f512b07830532eba72a85.
Safety review retained in safety-review.txt. Seal read-only scope only. Before D4-C require dedicated adversarial coverage for overlapping/case-colliding paths, file/directory collisions, historical originals, protected migration, conflicts and concurrent evidence drift. Global blocked status must supersede individual proposed rows. No sealed executable plan or atomic live snapshot. Actual candidate compatibility remains unverified. No production writes, pin changes, GUI integration, push or release.

## D4-B2 — Adversarial manifest safety validation
Baseline 642fd4718d1c0c883a2e8ce67c14c7505353a8a8. Global blockers convert all Install/Replace/Remove rows to Block; preserved settings remain untouched. Changed or obsolete protected payload requires explicit migration review. Added case-folded ancestor collision checks, copied state sample, repeated installed/ownership recognition, archive digest/identity and target/ancestor identity rechecks.
Expanded both existing synthetic cross-game fixture methods with overlapping packages, case-only filename/ancestor collisions, file-directory collisions, existing case twins, symlink destination, historical originals, new/changed/missing protected files, known conflicts, state drift, late destination and candidate drift. Global blocking assertions and non-authorization checked; independent recheck 2/2. Targeted 83/83 (1.290s); full 1876/1876 (101.804s), process 10465 exit 0. Historical audit 38 manifests/214 entries, ERVR 20, nested D1, two reboot fixtures, 121 Fatekeeper files; all recipe TOMLs unchanged. Stable state unchanged, gate closed.
Evidence: ~/NAnnersVRhub-recovery/Dev5G-A6.7D4B2-full-AIqUDu.
Manifest SHA-256: 4bcfd1fb3468e58919631c62f7ca69302c206d1ab807293d1821a08e2acd4d31.
Limitations: repeated sampling is not an atomic snapshot or proof against all races; adversarial fixtures simulate upstream evidence. Execution-time sealed identity, complete backups, explicit ownership publication and rollback remain D4-C requirements. No production writes, pin changes, GUI integration, push or release.

## D4-C1 — Fixture-only managed update transaction foundation
Baseline e91fede37f496fdce333a43c27bf50f7b08d25d2. Added synthetic ZIP-pair rehearsal with private recipe copies and schema-accurate historical ownership in private temporary fixtures. Reuses hardened manifest and unchanged offline transaction engine. Exact add/replace/delete scope and hashes bound to reviewed plan; fresh manifest comparison before execution; full recorded fixture inventory backed up and verified. Both games exercise commit/rollback, interruption after backup and stale archive, incoming payload, state, save and newly occupied destination rejection. Preserves customized config, bindings, original backup, unrelated mods and saves.
Initial targeted 7/7 (0.631s), expanded targeted 51/51 (19.920s), full 1883/1883 (99.282s), process 13219 exit 0. Historical audit 39 manifests/223 entries, ERVR 20, nested D1, two reboot fixtures, 121 Fatekeeper files; all production recipe TOMLs and offline transaction engine unchanged. Stable state unchanged, gate closed.
Evidence: ~/NAnnersVRhub-recovery/Dev5G-A6.7D4C1-full-Sf2aQV.
Manifest SHA-256: 9d8af5332339fd078f52ced5ec533590759b122ee53df4f95792c53d60a74528.
Scope: physical fixture file operations only; historical Hub package state deliberately remains unchanged on commit. D4-C2 must publish updated ownership transactionally before any integrated update workflow. Candidate archives and metadata synthetic; repeated sampling and plan verification do not eliminate all races. Full independent-process interruption matrix and realistic full pinned inventories remain pending. No production writes, pin changes, GUI changes, push or release.

## D4-C2 — Fixture-only transactional ownership publication
Baseline bfeb86d329f6f758228f7abf3fe660e6addc7d4c. Updated fixture ownership is included in the same sealed transaction plan as dependency additions, replacements and deletions. Package archive name and digest, managed paths and expected payload hashes are updated; unchanged loader record, historical originals, unrelated game record and customized configuration/binding bytes preserved. Expected package hashes are not rebased to customized bytes. Offline engine ordering explicitly places hub/state.json last among incoming operations; reverse rollback restores it first.
Six new tests across Subnautica and Valheim validate publication, exact rollback, interrupted dependency/publication/inventory boundaries and tampered incoming state refusal. Initial targeted 13/13 (1.149s), expanded targeted 57/57 (20.395s), full 1889/1889 (97.450s), process 14622 exit 0; independent ownership recheck 6/6 (0.556s). Historical audit 40 manifests/231 entries, ERVR 20, nested D1, two reboot fixtures, 121 Fatekeeper files. All production recipe TOMLs, BepInEx installer and Fatekeeper authorization code unchanged; stable state unchanged, gate closed.
Evidence: ~/NAnnersVRhub-recovery/Dev5G-A6.7D4C2-full-LuCuwB.
Manifest SHA-256: 79bbd8559a04e5565f04f0fa41281ed09b5579692fbd4660b6092d2654a487c9.
Scope and limitations: simulated candidate metadata and ZIPs; ownership published only in disposable fixtures. In-process injected interruptions are not independent-process or power-loss validation. Updated record uses existing archive/digest schema, not a new independently verified version field or production pin. Independent-process recovery and complete pinned inventory rehearsals remain pending. No production writes, pin changes, GUI changes, push or release.

## D4-C3 — Persistent managed update interruption and recovery
Baseline 8ad95c6becc4e71ec69574eacedba954d1289ecd. Added independent-process fixture test harness transferring the parent's original serialized sealed plan to the child, rather than rebuilding it. Both games exercise 14 application interruption points, five interrupted recovery points, 11 tamper scenarios, four stale-plan scenarios and one explicit committed rollback scenario per game (70 matrix scenarios total, plus two initial fixture inspection contexts). Verify exact bytes, modes, directory layout, ownership inventory and idempotent recovery; verify original ownership restored first on interrupted rollback. Refuse stale parent plan and unexpected recovery edits.
Initial targeted 10/10 (7.588s), expanded targeted 67/67 (27.971s), full 1899/1899 (104.939s), process 16260 exit 0. Pre/post regression historical audits identical: 41 manifests/240 entries, ERVR 20, nested D1, two reboot fixtures, 121 Fatekeeper files, all four original pinned archives and four preserved copies match. All production recipes, installer, authorization module and offline transaction engine unchanged; stable state unchanged, gate closed.
Evidence: ~/NAnnersVRhub-recovery/Dev5G-A6.7D4C3-full-XpdY9V.
Manifest SHA-256: 85a57bb34c15584d9b4f9d878bfeeba0280f37abd8ea95596ecbd7dc2d144fb1.
Scope: test-only change; simulated interruptions followed by process exit after exception unwinding, not arbitrary termination or power-loss testing. Child validates original serialized transaction plan and fixture content, not independent upstream discovery or fresh archive validation. Synthetic candidate releases remain unverified for real compatibility. Complete pinned inventory update rehearsal remains D4-C4. No production writes, pin changes, GUI changes, push or release.
