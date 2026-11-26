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
