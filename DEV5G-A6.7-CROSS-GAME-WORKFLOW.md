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
