# NAnnersVRhub

A Linux VR mod hub for Steam games (built on CachyOS + WiVRn + Quest 3).

Run the window (needs `sudo pacman -S pyside6`), from this folder:

    python -m vrhub.gui

Or use the command line:

    python -m vrhub.cli status
    python -m vrhub.cli install ready-or-not --file ~/Downloads/<mod>.zip
    python -m vrhub.cli install fatekeeper --file ~/Downloads/UEVR_FK.zip
    python -m vrhub.cli install-profile fatekeeper --file ~/Downloads/SLASHER-Win64-Shipping.zip
    python -m vrhub.cli launch-injector fatekeeper
    python -m vrhub.cli info fatekeeper        # the setup checklist
    python -m vrhub.cli updates                # check for newer releases
    python -m vrhub.cli mark-current fatekeeper
    python -m vrhub.cli nexus-key              # save a free Nexus API key (hidden prompt) for Nexus update checks

Each game is a recipe in `recipes/*.toml`. The code package is still called `vrhub`
(so existing commands keep working); only the display name changed.
