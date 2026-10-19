# NAnnersVRhub troubleshooting

## Collect useful evidence

Select the game in Games -> Compatibility profile -> Create support report.
Choose Text or JSON, review the captured time and export options, then Copy or
Save. Home-prefix replacement is on by default; paths outside that home and
personal data in notes/excerpts may still remain. Excerpt-free exports preserve
counts, source metadata and last matching-entry metadata.

**Collect new snapshot** reads the sources again. Copy/Save export the existing
snapshot; closing a game does not refresh it or delete logs. Collection is
read-only and does not start an OpenXR session, set a runtime, install mods or
record a gameplay result. Existing report destinations are preserved.

## Interpret the labels

| Label | Meaning |
| --- | --- |
| HOST CHECKS PASSED | Required host prerequisites passed; current gameplay/controllers are not certified |
| HEADSET CONNECTED | WiVRn's read-only property reports a connection; not proof of rendering or input |
| LOCAL CHECKS PASSED | Measured game configuration checks passed |
| REVIEW REQUIRED | Manual checks remain, such as actual Steam options/in-game settings |
| INCOMPLETE / NOT READY | Unknown or failed configuration checks need review; inspect the named findings |
| RECOGNIZED LOG EVIDENCE | A known signature appeared in inspected historical log content |
| NO KNOWN SIGNATURES FOUND | The bounded tail has none of the small known signature set; other errors may remain |
| COMPLETE / PARTIAL support collection | All section collectors returned data, or at least one failed; not a gameplay verdict |
| Local gameplay SUCCESS/PARTIAL SUCCESS/FAILURE | An explicit saved user report for its recorded date/setup; not automatic verification of another session |

Missing logs or empty history remain explicitly missing. A bundled dated
reference is separate from the selected game's local records. Preserve an
earlier successful test when reporting a later failure; add a new record with
the checks you performed and useful notes. A newer record is shown first.

## Times, counts and old errors

Readable/interface times use the computer's local timezone in 24-hour format;
JSON source timestamps retain their original ISO values. Bundled date-only test
references stay dates. To inspect the desktop's timezone in fish:

```fish
date '+%Y-%m-%d %H:%M:%S %Z %z'
```

Literal log excerpts are not rewritten. A log timestamp without an offset/zone
is labelled timezone not recorded, even if it resembles the desktop clock. File
modification time is separate and does not identify a session. A recent log may
contain old failures; an older log may remain after the game closes.

Counts apply to the inspected tail: at most 512 KiB per file, four explicit
files, 10,000 retained lines, and 4,096 characters per line. A count such as 462
validation failures means repeated matching log entries, not 462 different
bugs. The last matching-entry metadata describes file order in that tail; it
does not establish that the error is still occurring or has permanently stopped.

`XR_ERROR_VALIDATION_FAILURE` means an OpenXR call failed validation; repeated
xrEndFrame failures show rejected submissions, without identifying the invalid
parameter. `XR_FRAME_DISCARDED` from xrBeginFrame is a positive OpenXR status,
despite some applications labelling it failed/error. Treat it as context for
nearby rejected submissions. Dev6-fix1 and later recognize both patterns.
The API definitions are in Khronos's
[XrResult reference](https://registry.khronos.org/OpenXR/specs/1.1/man/html/XrResult.html)
and [xrBeginFrame reference](https://registry.khronos.org/OpenXR/specs/1.1/man/html/xrBeginFrame.html).

## Existing game workflows and confirmed test conditions

### Fatekeeper

Use the existing game prefix and Proton selection. Connect through WiVRn,
launch into gameplay, run the recipe's UEVR_FK injector, select the game process
and OpenXR, then inject. The recipe documents .NET Desktop Runtime and Frame
Generation checks; these are not inspected automatically.

The October 18 user-confirmed sequence is **2D Screen Mode OFF**, then close the
in-game UEVR overlay with **Insert** before evaluating immersion. The reported
controller shortcut also opened WayVR's menu, so use Insert for this test.
Closing the overlay is distinct from closing the desktop injector window. The
workaround is evidence from one setup, not proof of the frame-validation bug's
exact cause.

The expected log is the game prefix's
`drive_c/users/steamuser/AppData/Roaming/UnrealVRMod/SLASHER-Win64-Shipping/log.txt`.
Community builds can use another path; choose the actual file explicitly.

### Cyberpunk 2077

The recipe remains experimental. Connect WiVRn and use the installed prerequisite
mods plus phase-2 VR port. Review the actual Steam DLL override/runtime-import
settings; host environment values do not prove Steam used them.

The tested workaround has F10 -> General -> VR menu quad OFF, HUD -> Enable HUD
panel OFF, and World-space interactions/dialogs OFF. Close F10 fully before
evaluating gameplay. The user reported game-menu passthrough returning to full
VR after exiting that menu. Its exact underlying fault remains unconfirmed.
The primary plugin log is `bin/x64/cyberpunkvrport.log`; choose RED4ext/CET logs
explicitly when investigating their loaders.

### Ready or Not

Use the VRO workflow and the existing DirectX 11 selection/recipe fallback.
Check the actual launch options and aim-assist setting described by the guide.
Load a mission before pressing U for VR; Home exits VR. Recorded VRO package
inventory does not prove current package loading. Dev8 has no automatic log
path for this game; choose a known log explicitly if needed.

### Skyrim VR / Mad God's Overhaul

Use the Jackify MO2 Steam shortcut, its own prefix and configured Proton, then
the selected SKSEVR entry. GE-Proton10-14 is a dated reference, not a forced
version. Keep exactly one recognized bundled OpenComposite variant enabled in
the active MO2 profile, with its folder present, and recognized VR Performance
Kit variants disabled. Host xrizer selection does not prove which game DLL loads.
Jackify/Wabbajack remains responsible for installing/updating MGO. Choose logs
explicitly; the Hub does not guess a log path between the MO2 and base prefixes.
