Safer installation recovery, development save tools and an accessible Hub rollback control.

### What changed

- Add development-only save backup, snapshot history, file comparison, whole-folder restore, Undo last restore and remembered custom folders for the nine bundled profiles. Development tools start disabled each session; sources and targets are explicitly selected.
- Reject redirected/replaced save folders and altered recovery copies; verify recorded hashes before restoration. Explain blocked backups and list recent recovery sets without silently hiding their saved copies.
- Improve recovery layout with side-by-side details and scrolling. **Adjustable 70%/80%/90%/Custom sizing applies only to the development save recovery window.**
- Retain original files for new PAK installs, restore them on uninstall, protect state commits and retain recovery copies when rollback is incomplete.
- Add **Roll back to [version]** and explicit **Restart Hub** in Hub updates, with confirmation, previous-release verification and stale-confirmation checks.
- Add **GPLv3 (GPL-3.0-only)** licensing for original Hub code. The existing MIT bridge installer and separately obtained dependencies/mods keep their own terms.

### Install or update

Existing managed installations: after publication, use **Hub updates → Check now → Download source ZIP → Install update → Restart Hub**.

For manual installation, download the custom **NAnnersVRhub-0.5.4-source.zip** (or tar.gz) and **SHA256SUMS**, verify the checksum, extract, close the old Hub and run `python3 install.py`. Game installations, saves and test history remain separate from application activation. The optional KHARVOX bridge remains separately versioned and installed.

### Validation and limitations

The final 0.5.4 build passed **598 automated tests**, plus managed upgrade and two-way rollback checks from 0.5.3 and RC1 with nine recipes and seven fixture files preserved. RC1 passed the user-reported desktop check, and the dev23 rollback cancel/accept/restart workflow passed on the user desktop. Evidence is included in VALIDATION-0.5.4.md and its accompanying records. No new gameplay success or published-endpoint update is claimed by release preparation.

Development save recovery checks file sets and integrity, not game progress or save/mod compatibility. Close games/launchers and stop cloud synchronization before replacement. No backup is automatically deleted and no newest save is automatically chosen.

Two earlier medium installer issues—profile replacement failure recovery and stale files after injector replacement—remain deferred. Legacy backups absent from older versions cannot be recreated. Remove new pak-1 installs using a compatible Hub version before rolling back to an older version without that metadata support. See RELEASE-NOTES-0.5.4.md for full scope and limitations.

Built with AI assistance, hands-on user tests and automated checks. Compatibility reports remain setup- and version-specific.
