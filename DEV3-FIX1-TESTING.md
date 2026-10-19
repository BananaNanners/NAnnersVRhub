# NAnnersVRhub 0.5.0-dev3-fix1

The first dev3 report incorrectly required the older Open Composite XR mod.
The user's active profile instead enables:

```text
-VR Performance Kit - FSR - Use with DLAA
-VR Performance Kit - CAS Sharpening - Default
+Open Composite Unleashed for Skyrim VR 171182 5.0.4 2026
-Open Composite XR - Incompatible with VR Performance Kit
```

Fix1 recognizes this configuration. It does not switch mods or change Steam,
MO2, Proton, or the game files. Recognition is based on the active modlist and
matching mod folder; it does not prove which DLL is loaded during gameplay.

## Run the complete source

Download/extract the new ZIP in Downloads, then run:

```fish
cd ~/Downloads/NAnnersVRhub-0.5.0-dev3-fix1
python -m unittest discover -s tests -v
python -m vrhub.gui
```

Connect through WiVRn, select Games -> Skyrim VR/MGO -> Compatibility profile,
then Refresh compatibility -> Copy compatibility report. Paste that report.
Expect the enabled Unleashed variant to be named in Active-profile OpenComposite,
and both disabled VR Performance Kit variants to pass. If all previously
passing checks still pass and the Unleashed folder is present, expect
LOCAL CHECKS PASSED. Leave the working MO2 mod selection as it is.

After reviewing the report, use the normal Skyrim VR launch and verify rendering
and both controllers. The configuration snapshot alone is not a new gameplay test.

## Detection changes

- Accept either the old XR entry or Open Composite Unleashed for Skyrim VR.
  Unleashed may have numeric version/ID tokens appended, as in the reported name.
- Require the enabled variant's own mod folder. Another installed but disabled
  adapter folder cannot substitute for it.
- Report multiple enabled recognized adapter variants as requiring attention.
- Detect the FSR/DLAA and CAS/Default VR Performance Kit names from the actual
  profile, alongside the original legacy conflict names.
- Disabled VR Performance Kit folders no longer produce a review notice when
  their disabled state is established from the active modlist.
- Missing, custom-root, duplicate or unreadable modlists stay unverified.

## Optional patches for an existing checkout

Choose one patch; do not apply several:

| Current source | Patch |
| --- | --- |
| Original 0.5.0-dev3 | dev3-fix1-from-dev3.patch |
| 0.5.0-dev2 | dev3-fix1-from-dev2.patch |
| Clean v0.4.0 (2e320ac) | dev3-fix1.patch |

For original dev3, from your development repository:

```fish
git status --short
git apply --check ~/Downloads/NAnnersVRhub-0.5.0-dev3-fix1/dev3-fix1-from-dev3.patch
git apply ~/Downloads/NAnnersVRhub-0.5.0-dev3-fix1/dev3-fix1-from-dev3.patch
python -m unittest discover -s tests -v
python -m vrhub.gui
```

Preserve unrelated local work. If the check fails, stop and share the error.
The standalone source package can be tested without touching the checkout.

## Validation

97 unit tests pass, including the exact reported four modlist entries, an
Unleashed-only install, a missing enabled-variant folder, both adapters enabled,
both newly identified VR Performance Kit conflicts, and disabled-folder handling.
The GUI smoke check confirms the Unleashed result is displayed/copied and changes
to NOT READY when a conflict is enabled in the fixture. The extracted source and
all three patch baselines were verified before delivery. Live testing remains
on the user's machine.
