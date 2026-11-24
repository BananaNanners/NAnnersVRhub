# Dev5E1 — Hogwarts Legacy controlled update pilot

Starting checkpoint `4c3a0e18e1317e00143b9519e32726be8a82927c` on
`dev/0.5.5-fatekeeper-backend`.

The player can inspect each proposed file action in the existing profile review.
Live installation is blocked pending compatibility evidence.

## Exact dependency and file decisions

- Official [Hogwarts Legacy v2.1.0 release](https://github.com/jbusfield/HL_UEVR/releases/tag/v2.1.0),
  asset `HogwartsLegacy.zip`, 67,238,017 bytes, SHA-256
  `d2fb2b74db85dc2bab039063b367016a4a30fe5dfd509bb3480da0a0cde87efb`.
- Official [v2.0.6 baseline](https://github.com/jbusfield/HL_UEVR/releases/tag/v2.0.6),
  SHA-256 `30d7e626882bb3a7e1d04d8a42fd4f4bbcda9011054c4b12bf9e6e722dab06a3`.
  The stable and preview ownership records identify the same 192 profile files.
  Of these, 187 match the official baseline and five are modified locally.
  The profile also contains one unowned log.
- [Exact manifest](DEV5E1-HOGWARTS-MANIFEST.tsv) lists 36 Install, 53 Replace
  and 140 Preserve decisions. Each Replace matches the old release hash.
  Preserves cover 134 already-matching files, five modified files and `log.txt`.
- Preserve `cache/sdk_discovery.json`, `config.txt`, `data/config_default.json`,
  `data/hogwarts_legacy_config.json` and `imgui.ini`. Keep `config.txt` active
  and leave `config_AFW.txt` as its own optional v2.1.0 file. The joeyhodge
  backend and `LuaVR.dll`, Heroic runner and Proton prefix are outside the
  write manifest.

## Compatibility and gate

The maintainer recommends removing the old profile before importing v2.1.0.
The candidate replaces `uevr_utils.dll` and `voice_recognizer.dll` inside
the profile alongside main, input, gesture and attachment Lua and their
parameters. The shipped `data/config_default.json` adds
`uevr_input_config_autoDetectEyeIndices`, and `data/hogwarts_legacy_config.json`
adds 15 top-level keys including stick drift, flick casting and holster.
The incoming main Lua references the new flick-casting and holster settings.
The preserved local JSON lacks those keys. Existing attachment parameter
files proposed for replacement match the old official hashes. The review
has no runtime evidence confirming safe defaults for the preserved JSON or
correct input, gestures, attachments and plugin interactions in the merged
profile. Keep the live gate closed.

## Verification

- Focused tests 49 passed. Full regression 1,516 run, 1,515 passed, one skipped.
- Disposable transaction exercised all 89 planned profile writes and a
  separate copied Hub record update with the exact candidate bytes.
  The complete SHA-256-verified backup covered 193 profile files, their
  directory tree and the original Hub state document. Explicit rollback,
  interruption after write 17, and interruption after updating ownership
  inventory each restored every original byte, ownership inventory and
  directory layout. The source profile and Hub record remained unchanged.
- Shared preview state produces the same 229-row review and keeps
  confirmation disabled. Fatekeeper and Hogwarts Legacy were discoverable.
  Interactive KDE player acceptance remains separate from automated tests.

After the pilot review, the separately tracked Fatekeeper backend dependency can
be revisited with player approval. Hogwarts live installation remains blocked.
