# Controller bindings — introduced in dev4, corrected in dev5

Dev4 added **Games → Controller bindings** to all seven game profiles. Dev5
corrects the Fatekeeper shortcut and the user-reviewed Vanilla Skyrim reference.
It is an offline reference: it does not change button assignments, mod settings,
test history, Steam/Heroic settings or game saves.

## Install and open (fish)

Close the running Hub, then:

```fish
unzip -n ~/Downloads/NAnnersVRhub-0.5.3-dev5-source.zip -d ~/Downloads
and cd ~/Downloads/NAnnersVRhub-0.5.3-dev5
and python install.py
and ~/.local/bin/nannersvrhub
```

The managed install switches the application release and retains the previous
release for rollback. There is no new GitHub release or automatic update yet.

## Check the page

1. Confirm all seven games and your existing test history are present.
2. Select each game and open **Controller bindings**. The reference must match
   the selected game; changing games clears the search and section filter.
3. In Valheim, select **Building** or search `rotate`. The grip + stick rotation
   combination is a documented default, explicitly unconfirmed on this setup.
4. Click **Expand…** for a larger window. Each expanded window is a reference
   for the game shown in its title, even if you later select another game.
5. Click **Copy full guide**. The clipboard includes every section, evidence
   label, note and source, even when the visible table is filtered.

## Evidence labels

| Label | Meaning |
| --- | --- |
| User tested | This control or workflow was reported working on the project setup. It does not verify another session. |
| Mod default | The mod author’s documentation or binding file specifies this mapping; local button-by-button confirmation may be absent. |
| Profile dependent | The mapping requires a specific preset or active configuration. |

The diagram identifies physical Quest / Touch buttons. It is a button-location
key, not a claim that every button has the same action in every game. L3/R3 mean
pressing the thumbstick. Keyboard shortcuts are explicitly labelled.

## Coverage and limits

- **Subnautica:** stock Y/PDA, tested A/trigger interaction and A-drag quick
  slots; no custom system-button override. The in-game binding editor was
  reported to get stuck and remains unsuitable for the tested workflow.
- **Valheim:** stock movement, inventory, grab and documented building chords.
  October 20 user-reported core VR, both controllers and basic building passed
  during at least 30 minutes. Piece rotation remains a follow-up test.
- **Hogwarts Legacy:** movement, documented optional gestures and mounts, plus
  the user-tested spell drawing / wrist flick. A complete face-button map,
  voice, healing, defensive gestures and mount steering are not locally verified.
- **Fatekeeper:** the paired FK script and stock UEVR translation. Custom
  runtime remaps can change the physical buttons. Insert closes the in-game
  overlay; the user’s L2 + R3 controller shortcut also opened WayVR.
- **Cyberpunk:** on-foot, combat, vehicle and overlay contexts differ. The
  successful HUD/menu workaround and menu/passthrough limitation remain.
- **Ready or Not:** VRO author-documented command, equipment and weapon
  controls; no mixing with the unrelated UEVR profile. Full button mapping
  depends on the installed build/handedness and its tablet prompts.
- **Skyrim MGO:** user-reviewed Vanilla Quest / Touch layout with the explicit
  trigger-ready exception: neither trigger draws a sheathed weapon; normal
  combat/casting remains once readied. Left grip readies/sheathes, right grip
  shouts, A activates and L3 sprints. The guide does not change installed bindings.

Source links and version/scope notes are bundled with each guide. Opening a
source link requires a browser connection; reading/filtering/copying does not.

The Valheim bundled reference records the October 20 user report. Its saved
NOT READY runtime snapshot remains historical scan-time evidence; it is not
rewritten, and the guide does not infer a current headset connection.
