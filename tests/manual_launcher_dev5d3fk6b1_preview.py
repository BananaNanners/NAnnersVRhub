# SPDX-License-Identifier: GPL-3.0-only
"""Full Hub acceptance preview with user-initiated game and injector launches."""
import os
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel

from tests import manual_launcher_dev5d3y3_preview as base
from vrhub import hub, launch_environment
from vrhub.dev_preview_storage import shared_directory


class FullHubPreview(base.PlayerFirstPreview):
    def disable_mutations(self):
        super().disable_mutations()
        recipe = self.current()
        if recipe:
            self.game_play_btn.setEnabled(bool(hub.game_play_label(recipe)))
            self.inject_btn.setEnabled(recipe.get("method") == "uevr")

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.identify_preview)

    def identify_preview(self):
        self.setWindowTitle("NAnnersVRhub Dev5D3-FK6B1 - Full Hub Preview")
        brand = self.findChild(QLabel, "brandTitle")
        if brand:
            brand.setText("NAnnersVRhub - FK6B1 Preview")
        print("FK6B1 full KDE Hub visible; live mod writes gated", flush=True)


def main():
    launch_environment.capture_host_xdg()
    shared = shared_directory()
    os.environ["VRHUB_STATE"] = str(shared / "state.json")
    os.environ["VRHUB_NEXUS_KEY_FILE"] = str(shared / "test-nexus-key")
    for key, folder in (("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"),
                        ("XDG_CACHE_HOME", "cache")):
        os.environ[key] = str(shared / folder)
    base.PlayerFirstPreview = FullHubPreview
    sys.argv = [sys.argv[0], "--show"]
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
