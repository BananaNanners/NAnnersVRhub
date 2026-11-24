# SPDX-License-Identifier: GPL-3.0-only
"""Full Hub Dev5E2 corrective preview: integrated backend install guidance."""
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel

from tests import manual_launcher_dev5d3fk6b1_preview as full


class FatekeeperInstallPreview(full.FullHubPreview):
    def identify_preview(self):
        self.setWindowTitle(
            "NAnnersVRhub Dev5E2 - Fatekeeper Backend Install / Update")
        brand = self.findChild(QLabel, "brandTitle")
        if brand:
            brand.setText("NAnnersVRhub - Dev5E2 Install Preview")
        for index, row in enumerate(self.rows):
            recipe = row["recipe"]
            if recipe["id"] == "fatekeeper":
                self.sidebar.game_list.setCurrentRow(index)
                self.game_details_tabs.setCurrentWidget(self.downloads)
                self.downloads.set_recipe(recipe)
                # The base full Hub restores its last selected tab on show.
                # Switch after that queued restore rather than adding a tab.
                QTimer.singleShot(300, self._show_install_review)
                status = self.downloads.backend_install_status.text()
                print("DEV5E2 Install / Update status:", status, flush=True)
                print("DEV5E2 Fatekeeper archive roles: two; live mod writes gated",
                      flush=True)
                break

    def _show_install_review(self):
        self.game_details_tabs.setCurrentWidget(self.downloads)
        print("DEV5E2 selected tab:",
              self.game_details_tabs.tabText(self.game_details_tabs.currentIndex()),
              flush=True)


if __name__ == "__main__":
    full.FullHubPreview = FatekeeperInstallPreview
    raise SystemExit(full.main())
