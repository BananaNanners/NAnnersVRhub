# NAnnersVRhub 0.5.3 — release preparation

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
passed. Subnautica and Valheim have their earlier user-tested reports. This
does not certify other machines or every individual controller action.

Before publication: accept rc1 import/launch/history preservation, publish the
bridge asset at its pinned URL, merge the approved Hub release changes, build
the final 0.5.3 custom source ZIP plus SHA256SUMS, then test the published
0.5.2 -> 0.5.3 update on the user's desktop. RCs remain pre-releases and are not
served through the stable updater. Public release creation is pending.
