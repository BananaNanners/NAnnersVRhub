# Live in-app update acceptance: dev4 → 0.5.2

Keep **0.5.2-dev4 installed** for this test. Do not run the final source
installer first: that would leave no newer version for the updater to install.
The test becomes available after the official **v0.5.2 stable release** and
both custom assets are published. A draft or prerelease is intentionally
ignored. Until then, Check now can still show the older 0.5.1 stable release.

1. Open the installed Hub using its application-menu entry or
   `~/.local/bin/nannersvrhub`, not `python -m vrhub.gui` from a source folder.
2. Open **Hub updates… → Check now**. Expect **0.5.2 available**. If GitHub
   has not exposed the release yet, wait and choose Check now again.
3. Choose **Download source ZIP**. Expect a verified download and the 0.5.2
   release notes. Close/reopen the update window to check cached recovery if
   desired; the current application version remains dev4.
4. Choose **Install update…**, review its confirmation and accept. Expect
   **Installed 0.5.2** and an enabled **Restart Hub** button. The running window
   remains dev4 until restarted.
5. Choose **Restart Hub**. Expect the new title **NAnnersVRhub 0.5.2**, all five
   games, previous local test history and existing mod inventories.
6. Open Hogwarts Legacy through Heroic, then use **Run UEVR injector** as in
   the accepted dev4 test. Confirm the launch still works and saves are present.
7. Optional recovery check: close the Hub, run
   `~/.local/bin/nannersvrhub-manage rollback`, then reopen it and expect dev4.
   Close again and repeat rollback to return to 0.5.2. Both versions should
   retain the same saved data.

Report the displayed version, whether download/install/restart completed, and
whether the five games, history and saves remained intact. A failed check or
download should leave dev4 usable; retain the error text if anything fails.

Automatic download is optional. Leaving it off and clicking Download source
ZIP manually is enough to test the complete update route. This test does not
replace game-specific rendering, control or long-session tests.
