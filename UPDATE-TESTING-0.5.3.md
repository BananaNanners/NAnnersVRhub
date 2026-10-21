# Published 0.5.2 -> 0.5.3 update check

The rc1 user report at 2026-10-21 13:18:34 PDT passed bridge import, bridge
test, DOOM launch, VR rendering, head tracking, controllers and stereo depth.
The configuration snapshot at recording also passed. This is distinct from
an update through the live stable-release endpoint.

After bridge 0.2.0 and Hub 0.5.3 are published:
1. From an existing managed 0.5.2 installation, open Hub updates, Check now,
   Download source ZIP, Install update and Restart Hub.
2. Confirm the title is 0.5.3, all nine profiles appear and local history remains.
3. In DOOM use Install VR runner. A verified cached component/runner should be
   reused; a clean component state fetches the exact published bridge archive.
4. Connect WiVRn, Test VR bridge, then Launch DOOM VR and SFS. Check loaded
   gameplay and one other game. Saves and prior test history must remain.

Do not remove the known working runner just to test a clean install. Host
checks, import tests, cached reuse and fresh-machine gameplay are separate
claims. This step has not been marked passed by the rc1 offline-import report.
