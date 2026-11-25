# Dev5E8 — Production transaction integration (unreleased)

Accepted baseline: aa371e1f29f8991449e265cdf1f016470cb35ba6.
Global production gate remains false. No live game writes or publication.

## Verified implementation and tests

- Gated production install/recovery now use the shared persistent authority
  ledger, bound to resolved destination and independent private authority
  directory ~/.local/share/nannersvrhub-transaction-authority.
- Initial staging retry retains abandoned backup files, including on existing
  installation repair. Untrusted journal, missing/corrupt/redirected authority,
  unexpected initial staging entries and finalized stale journal are refused.
- Existing transaction engine retains backup/history and ownership protections.
  Production recovery checks the exact trusted journal before restoring.
- Thirteen additional tests: seven production safety and six independent-process
  cases. Subprocess exit during applying, payload writes, rollback and initial
  intent tested; terminal intent ambiguity deliberately fails closed.
- Tests use disposable destinations, synthetic dependency payloads and patched
  gate/resolver/preflight/game guard. No live gate modification.
- Initial 82/82, dedicated 97/97, expanded targeted 103/103 (14.777 s).
- Full discovery reported 1655 tests, OK (skipped=1), 49.627 s, exit 0.
  KHARVOX BridgeTests setUpClass skipped without verified standalone payload.
  No failures or errors. No GUI source changes.
- Protected inventory: 11 injector files, 110 profile files, one stable Hub
  state file; all 122 regular-file names, SHA-256 and modes matched before/after.
  Symlinks, saves and unrelated prefix files excluded.
- Stable state SHA-256:
  e4000197b5a4cf153e59c18058075d2a9dc312bbe2e3ff7519bae51c99370ef5.
- Evidence: ~/NAnnersVRhub-recovery/Dev5E8-evidence-WEJX1U
  Six byte-for-byte verified files, 401992 bytes. Manifest SHA-256:
  a94b3619c96d1a8806f7a0ce0b3ef99b1db97c9e7c63a5003570a73820267fd2.

## Activation limits and remaining safety review

Development integration validated in fixtures, not production activation.
Do not flip the global gate. No real production install in E8.
Actual reboot/power-loss and device identity across remounts untested.
Authority is a cooperative application boundary, not protection against
same-UID rewriting both stores. Pending two-digest transitions other than
the tested terminal intent remain subject to replay ambiguity; terminal
intent requires manual review. Initial staging checks artifact metadata,
not original abandoned bytes. Existing finalized journal retries preserve
history but do not exhaustively classify all stray artifacts. A no-op with
a missing journal does not verify the ledger; missing-journal handling,
atomic temporary-file interruptions, explicit recovery confirmation binding,
and mount/ancestor identity checks require review before activation.
Legacy journals without provenance are not adopted. Full update/repair
after a previous managed transaction needs additional production-path
coverage. No actual reboot, live install, or gameplay acceptance implied.
KDE acceptance pending.

## Agreed player-first direction

Finish development acceptance, then review player-facing wording (Dev5F1),
setup guides (Dev5F2), controller bindings (Dev5F3), followed by end-to-end
game installation/gameplay acceptance (Dev5G) and release preparation.
Safety gates remain separately authorized. AGENTS.md records permanent
player-friendly wording, guide accuracy and controller evidence rules.
