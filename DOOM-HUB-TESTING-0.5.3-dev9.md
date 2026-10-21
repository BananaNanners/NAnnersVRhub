# DOOM Hub integration check — 0.5.3-dev9

Close DOOM, KHARVOX and the standalone lab before testing. Extract the complete
source tar.gz and run `python3 -m vrhub` from the extracted directory. This does
not install or update the managed Hub automatically.

1. Confirm all nine games appear and local gameplay-test history remains.
2. Select DOOM and review its dated 40-minute user report. It must not create
   a new local test record or claim all individual bindings were tested.
3. Choose the complete KHARVOX 1.4 folder if needed. Keep its extraction
   outside DOOM. The normal flat launch remains a Heroic launch.
4. Click Prepare VR runner with DOOM/KHARVOX closed. The existing standalone
   lab runner is verified and reused. The original Heroic runner is not patched.
5. Connect WiVRn and click Test VR bridge. Wait for the full pass. The random
   JSON result path appears before the probe starts. An older/missing/changed
   pass must block Launch DOOM VR.
6. Click Launch DOOM VR. In KHARVOX select the GOG installation and SFS, then
   Launch Game. Load a campaign save and test headset output, tracking and
   both controllers. This is the first live validation of the new Hub route.
7. Open DOOM diagnostics to find launch/probe/audit output and probe-results.
   Game log diagnostics automatically reads main/error and launch/probe logs;
   audit, intro and renderer logs can be selected explicitly. Logs are historical.
8. Switch to another game: the DOOM-only preparation/test buttons must hide.

For a managed install, run this build's `python3 install.py`, restart the
application-menu entry and repeat the DOOM launch. The source folder can be
moved away after installation; the bridge files must remain in the managed
release. Other game data, saves, state/history and standalone lab state stay
in place. Rollback changes Hub application files only; it does not undo the
user's existing standalone lab runner.

Older installed in-app updaters cannot install this larger preview: their
archive limits and resource-copy policy predate bundled bridge binaries.
Use the included installer. The new package's resource check rejects an
incomplete older-installer copy before activation. Nothing is published or
merged by this development archive.

Supported preparation source: pinned Proton-CachyOS11.0-20260703-slr x86_64.
Supported Heroic configuration: native ~/.config/heroic; custom or Flatpak
roots are rejected rather than launching an unrelated prefix.

The bundled lab code and binaries are unchanged from the successful lab
0.1.6 test. Its corresponding source and licenses are under
vrhub/assets/kharvox-lab-0.1.6. A bridge pass is a synthetic historical test;
it does not certify current rendering, stereo depth or gameplay.
