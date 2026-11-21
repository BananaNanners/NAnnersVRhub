# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""0.5.5-dev1: launcher navigation preserves the existing hub behavior."""
import unittest
from unittest import mock

from PySide6.QtWidgets import QApplication
from vrhub import hub, app_updates
from vrhub.gui import HubWindow
from vrhub.launcher_ui import SHORT_GAME_NAMES
from vrhub.theme import STYLESHEET, YELLOW, BLUE, GREEN, RED
from vrhub.app_update_gui import HubUpdateController


class LauncherShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.patches = [
            mock.patch.object(HubWindow, "check_updates"),
            mock.patch.object(HubWindow, "scan_setup"),
            mock.patch.object(HubUpdateController, "startup"),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.window = HubWindow()
        self.window.show()
        self.app.processEvents()
        self.addCleanup(self.window.close)

    def test_all_nine_recipes_have_sidebar_entries_and_original_table_rows(self):
        self.assertEqual(self.window.sidebar.game_list.count(), 9)
        self.assertEqual(self.window.table.rowCount(), 9)
        self.assertEqual(set(SHORT_GAME_NAMES), set(hub.load_recipes()))
        self.assertEqual(self.window.sidebar.game_list.currentRow(), self.window.table.currentRow())
        self.assertEqual(self.window.tabs.currentIndex(), 1)
        self.assertTrue(self.window.sidebar.games_button.isChecked())
        self.assertFalse(self.window.sidebar.system_button.isChecked())

    def test_sidebar_selects_real_recipe_not_a_second_source_of_truth(self):
        rows = self.window.rows
        idx = next(i for i, row in enumerate(rows) if row["recipe"]["id"] == "cyberpunk-2077")
        self.window.sidebar.game_list.setCurrentRow(idx)
        self.app.processEvents()
        self.assertEqual(self.window.table.currentRow(), idx)
        self.assertEqual(self.window.current()["id"], "cyberpunk-2077")
        self.assertEqual(self.window.game_banner.heading.text(), "Cyberpunk 2077")
        self.assertIn("Game ", self.window.game_banner.status.text())
        self.assertNotIn("VR Ready", self.window.game_banner.status.text())
        self.assertEqual(self.window.game_details_tabs.tabText(0), "Overview")
        self.assertEqual(self.window.game_details_tabs.tabText(4), "Compatibility")
        self.assertEqual(self.window.game_details_tabs.tabText(5), "Controller Bindings")

    def test_original_table_selection_syncs_back_to_sidebar(self):
        self.window.library_toggle.click()
        self.app.processEvents()
        self.assertTrue(self.window.library_panel.isVisible())
        idx = next(i for i, row in enumerate(self.window.rows) if row["recipe"]["id"] == "valheim")
        self.window.table.selectRow(idx)
        self.app.processEvents()
        self.assertEqual(self.window.sidebar.game_list.currentRow(), idx)
        self.assertEqual(self.window.game_banner.heading.text(), "Valheim")

    def test_sidebar_navigation_reuses_existing_vr_dashboard(self):
        self.window.sidebar.system_button.click()
        self.app.processEvents()
        self.assertEqual(self.window.tabs.currentIndex(), 0)
        self.assertTrue(self.window.sidebar.system_button.isChecked())
        self.assertIn("Scan your host VR setup", self.window.scan_summary.text())
        self.window.sidebar.games_button.click()
        self.app.processEvents()
        self.assertEqual(self.window.tabs.currentIndex(), 1)
        self.assertTrue(self.window.sidebar.games_button.isChecked())

    def test_all_existing_advanced_actions_are_accessible(self):
        self.assertFalse(self.window.more_tools_panel.isVisible())
        self.window.more_tools_toggle.click()
        self.app.processEvents()
        self.assertTrue(self.window.more_tools_panel.isVisible())
        for name in (
            "uninstall_btn", "profile_btn", "unprofile_btn", "verify_btn",
            "copy_btn", "inject_btn", "game_launch_btn", "inspect_btn",
            "diag_btn", "mark_btn", "key_btn",
        ):
            self.assertIsNotNone(getattr(self.window, name))
        self.window.game_details_tabs.setCurrentIndex(self.window.game_details_tabs.indexOf(self.window.compat_page))
        self.assertEqual(self.window.game_details_tabs.tabText(4), "Compatibility")
        self.assertIsNotNone(self.window.compat_refresh_btn)

    def test_sidebar_text_hierarchy_and_row_spacing(self):
        from PySide6.QtCore import Qt
        from vrhub.launcher_ui import GameLibraryItemDelegate
        self.assertIsInstance(self.window.sidebar.game_list.itemDelegate(), GameLibraryItemDelegate)
        self.assertGreaterEqual(self.window.sidebar.minimumWidth(), 230)
        first = self.window.sidebar.game_list.item(0)
        self.assertGreaterEqual(first.sizeHint().height(), 60)
        self.assertEqual(first.data(Qt.UserRole), "Cyberpunk 2077")
        self.assertIs(type(first.data(Qt.UserRole + 1)), bool)
        stylesheet = self.window.styleSheet()
        self.assertIn("QLabel#launcherSideTitle", stylesheet)
        self.assertIn("font-size: 16px", stylesheet)
        self.assertIn("font-size: 14px", stylesheet)
        self.assertIn("#FFD21A", stylesheet)

    def test_future_sections_expand_without_hiding_game_library(self):
        self.assertFalse(self.window.sidebar.future_panel.isVisible())
        self.window.sidebar.future_toggle.click()
        self.app.processEvents()
        self.assertTrue(self.window.sidebar.future_panel.isVisible())
        self.assertEqual(self.window.sidebar.game_list.count(), 9)
        self.window.sidebar.future_toggle.click()
        self.app.processEvents()
        self.assertFalse(self.window.sidebar.future_panel.isVisible())

    def test_unimplemented_navigation_is_disabled_and_labeled(self):
        for label in ("Downloads", "Backups", "Settings", "Logs"):
            button = self.window.sidebar.planned_buttons[label]
            self.assertFalse(button.isEnabled())
            self.assertIn("planned", button.toolTip())
        self.assertEqual(self.window.tabs.count(), 2)

    def test_brand_colors_preserved_and_game_title_uses_original_recipe(self):
        # Brand palette constants must remain unchanged; the launcher uses
        # yellow and blue, while green/red retain their existing status roles.
        self.assertEqual((YELLOW, BLUE, GREEN, RED),
                         ("#FFD21A", "#23B7FF", "#4FE39A", "#FF5B50"))
        self.assertIn(YELLOW, STYLESHEET)
        self.assertIn(BLUE, STYLESHEET)
        self.assertIn("QFrame#launcherGameBanner", STYLESHEET)
        self.assertIn("NAnnersVRhub", self.window.windowTitle())
        self.assertEqual(self.window.game_banner.caption.text(), "NANNERSVRHUB  /  GAME PROFILE")

    def test_refresh_keeps_selection_and_header_in_sync(self):
        idx = next(i for i, row in enumerate(self.window.rows) if row["recipe"]["id"] == "cyberpunk-2077")
        self.window.select_launcher_game(idx)
        self.window.refresh()
        self.assertEqual(self.window.table.currentRow(), idx)
        self.assertEqual(self.window.sidebar.game_list.currentRow(), idx)
        self.assertEqual(self.window.game_banner.heading.text(), "Cyberpunk 2077")


if __name__ == "__main__":
    unittest.main()
