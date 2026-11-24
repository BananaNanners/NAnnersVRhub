# SPDX-License-Identifier: GPL-3.0-only
"""Dev5E2 complete Hub preview: show the tested backend in existing Updates."""
from PySide6.QtWidgets import QLabel

from tests import manual_launcher_dev5d3fk6b1_preview as full
from vrhub import hub, updates


class FatekeeperBackendPreview(full.FullHubPreview):
    def identify_preview(self):
        self.setWindowTitle("NAnnersVRhub Dev5E2 - Fatekeeper Backend Dependency")
        brand = self.findChild(QLabel, "brandTitle")
        if brand:
            brand.setText("NAnnersVRhub - Dev5E2 Preview")
        for index, row in enumerate(self.rows):
            recipe = row["recipe"]
            if recipe["id"] == "fatekeeper":
                self.sidebar.game_list.setCurrentRow(index)
                self.game_details_tabs.setCurrentWidget(self.mod_updates)
                # Preview-only, local-only verification. The production Updates
                # page retains its existing user-initiated Refresh action.
                rows = updates.check_recipe(recipe, hub.state())
                self.update_results[recipe["id"]] = rows
                self.mod_updates.set_recipe(recipe, rows)
                section = self.mod_updates.sections["current"]
                if not section.disclosure.isChecked():
                    section.disclosure.click()
                print("DEV5E2 Fatekeeper backend:", rows[-1]["status"],
                      "with two archive dependencies; live mod writes gated", flush=True)
                break


if __name__ == "__main__":
    full.FullHubPreview = FatekeeperBackendPreview
    raise SystemExit(full.main())
