# 0.5.3-rc1 acceptance check

Download the custom Hub rc1 source ZIP and companion
NAnners-KHARVOX-Bridge-0.2.0-source.tar.gz. Close the Hub and install the rc1
application with its included install.py. Do not uninstall any game or runner.

1. Confirm the title is 0.5.3-rc1, all nine profiles appear, and existing local
   test history remains available.
2. Select DOOM -> Import bridge package… -> choose the companion source tar.gz.
   The archive checksum and every payload file are verified. Your existing
   isolated lab 0.1.6 runner should be reused without another base download.
3. Connect WiVRn -> Test VR bridge -> Launch DOOM VR -> KHARVOX SFS -> campaign.
   Check headset rendering, tracking, both controllers and stereo depth.
4. Restart from the application menu and repeat Launch DOOM VR. The component
   lives outside the download/source folder and must remain available.
5. Check one other game still launches normally and local history is intact.

Before bridge publication, Install VR runner cannot fetch its not-yet-public
GitHub asset. Use the explicit Import action for this RC. After publication,
Install VR runner uses that same pinned source archive automatically. The
new component distribution does not patch Heroic's original runner or game.

A container test exercises the actual published 0.5.2 updater, with synthetic
HTTP responses carrying this candidate under the future stable 0.5.3 label.
It checks old size/resource limits, download/verify/managed install, restart,
nine-profile loading without the optional component, two-way rollback and
fixture state/history/save preservation. That is not a public endpoint test.

After the final 0.5.3 release is published, use Hub updates from an existing
managed 0.5.2 install and confirm the real GitHub download/install/restart path.
