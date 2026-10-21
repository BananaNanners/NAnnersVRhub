# NAnnersVRhub 0.5.3

Add Subnautica, Valheim, experimental Elden Ring and GOG/Heroic DOOM (2016)
to the five profiles shipped in 0.5.2, along with controller references and
stronger package/version checks. Keep unsupported Elden Ring builds blocked.

DOOM uses the separately released NAnners KHARVOX Bridge 0.2.0. Install VR
runner verifies the complete component source/binary archive and exact base,
then prepares a separate runner. Test VR bridge records a synthetic probe;
Launch DOOM VR starts KHARVOX through the isolated runner and existing prefix.
The tested engine remains lab 0.1.6. Heroic's original selection stays in place.

The Hub source archive is kept small enough for the 0.5.2 updater and includes
only Python/image/TOML application resources. Other games work without the
optional bridge. Manual bridge import is available for offline setup and RC
checks. KHARVOX/game files are not redistributed.

Dated user evidence is scoped to each setup. DOOM dev9 passed VR rendering,
tracking, controller input and stereo depth; dev10 installation/test/launch
passed. The October 21 rc1 report (13:18:34 PDT) also passed Import bridge
package, Test VR bridge and Launch DOOM VR, with rendering, tracking,
controllers, stereo depth and the sampled configuration all passed.
Subnautica and Valheim have their earlier user-tested reports. This
does not certify other machines or every individual controller action.

The rc1 gameplay gate is accepted. Publication order: release the exact pinned
bridge 0.2.0 asset, merge the approved Hub release changes, then publish the
custom 0.5.3 source ZIP plus SHA256SUMS. After publication, test the real
0.5.2 -> 0.5.3 update on the user desktop. No online download is claimed for
the not-yet-published bridge asset; the accepted test used offline import.
Public repository/release creation remains pending.
