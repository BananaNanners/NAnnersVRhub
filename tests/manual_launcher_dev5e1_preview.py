# SPDX-License-Identifier: GPL-3.0-only
"""Show the complete Dev5E1 Hub on KDE using existing isolated preview state."""
from PySide6.QtWidgets import QLabel

from tests import manual_launcher_dev5d3fk6b1_preview as full


class HogwartsPilotPreview(full.FullHubPreview):
    def identify_preview(self):
        self.setWindowTitle("NAnnersVRhub Dev5E1 - Hogwarts Legacy Update Review")
        brand = self.findChild(QLabel, "brandTitle")
        if brand:
            brand.setText("NAnnersVRhub - Dev5E1 Preview")
        for index, row in enumerate(self.rows):
            if row["recipe"]["id"] == "hogwarts-legacy":
                self.sidebar.game_list.setCurrentRow(index)
                self.game_details_tabs.setCurrentWidget(self.downloads)
                break
        print("DEV5E1 full KDE Hub visible; live mod writes gated", flush=True)


if __name__ == "__main__":
    full.FullHubPreview = HogwartsPilotPreview
    raise SystemExit(full.main())
