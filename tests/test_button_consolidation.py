# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D1-B: fewer visible controls, all existing action handlers preserved."""
import unittest
from unittest import mock

from PySide6.QtWidgets import QApplication, QPushButton
from vrhub.app_update_gui import HubUpdateController
from vrhub.gui import HubWindow
from vrhub.downloads_gui import GuidedDownloadsPage


class ConsolidatedHubControlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        patch = mock.patch.object(HubWindow, "check_updates")
        self.mock_update_check = patch.start()
        self.addCleanup(patch.stop)
        for patch in (
            mock.patch.object(HubWindow, "scan_setup"),
            mock.patch.object(HubUpdateController, "startup"),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.win = HubWindow()
        self.win.show()
        self.app.processEvents()
        self.addCleanup(self.win.close)

    def switch(self, page):
        self.win.game_details_tabs.setCurrentIndex(
            self.win.game_details_tabs.indexOf(page))
        self.app.processEvents()

    def test_overview_has_only_two_primary_actions(self):
        self.switch(self.win.overview_page)
        self.assertEqual(self.win.quick_actions.buttons,
                         (self.win.game_play_btn, self.win.preflight_btn))
        # Small offscreen test desktops may use one compact column.
        self.assertIn(self.win.quick_actions._columns, (1, 2))
        self.win.resize(1630, 1060)
        self.app.processEvents()
        self.assertEqual(self.win.quick_actions._columns, 2)
        self.assertLessEqual(self.win.quick_actions.maximumWidth(), 760)
        self.assertTrue(self.win.library_toggle.isVisible())
        self.assertFalse(self.win.more_tools_toggle.isVisible())
        self.assertIs(self.win.refresh_library_btn.parent(), self.win.library_panel)

    def test_only_one_refresh_update_button_and_one_backend_connection(self):
        self.assertIs(self.win.check_btn, self.win.mod_updates.refresh_button)
        matches = [p for p in self.win.findChildren(QPushButton)
                   if p.text() == "Refresh update status"]
        self.assertEqual(matches, [self.win.mod_updates.refresh_button])
        self.mock_update_check.reset_mock()
        self.win.mod_updates.refresh_button.click()
        self.mock_update_check.assert_called_once_with()

    def test_actions_reparented_into_correct_pages_without_recreating_buttons(self):
        self.assertIs(self.win.install_tools_panel.parent(), self.win.downloads)
        self.assertIs(self.win.update_tools_panel.parent(), self.win.mod_updates)
        self.assertIs(self.win.more_tools_panel.parent(), self.win.compat_page)
        self.assertIs(self.win.uninstall_btn.parent(), self.win.rollback_page)
        self.assertIs(self.win.unprofile_btn.parent(), self.win.rollback_page)
        self.assertIs(self.win.doom_saves_btn.parent(), self.win.rollback_page)
        self.assertIs(self.win.profile_btn.parent(), self.win.install_tools_panel)
        self.assertIs(self.win.key_btn.parent(), self.win.update_tools_panel)
        self.assertIs(self.win.log_diagnostics_btn.parent(), self.win.more_tools_panel)

    def test_disclosures_are_initially_collapsed_and_open_only_in_own_tab(self):
        self.assertTrue(self.win.install_tools_toggle.isHidden())
        self.assertTrue(self.win.install_tools_panel.isHidden())
        self.assertEqual(
            self.win.downloads.layout().indexOf(self.win.install_tools_panel), -1)
        groups = (
            (self.win.update_tools_toggle, self.win.update_tools_panel, self.win.mod_updates),
            (self.win.more_tools_toggle, self.win.more_tools_panel, self.win.compat_page),
        )
        for button, panel, page in groups:
            with self.subTest(group=button.text()):
                self.switch(page)
                self.assertFalse(panel.isVisible())
                button.click()
                self.app.processEvents()
                self.assertTrue(panel.isVisible())
                self.assertTrue(button.isChecked())
                button.click()
                self.app.processEvents()
                self.assertFalse(panel.isVisible())

    def test_rollback_contains_development_only_save_tool_but_keeps_it_hidden(self):
        self.switch(self.win.rollback_page)
        self.assertFalse(self.win.doom_saves_btn.isVisible())
        self.assertFalse(self.win.unprofile_btn.isVisible())
        self.assertFalse(self.win.development_tools_enabled)
        self.assertIn("does not guarantee that files can be restored",
                      self.win.rollback_page.findChildren(
                          __import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel,
                          "rollbackNotice")[0].text())

    def test_installation_and_compatibility_keep_all_original_secondary_actions(self):
        # Legacy handler objects remain parked but never offered as
        # duplicate buttons. KHARVOX specialists live in Compatibility.
        install = ("install_btn", "profile_btn", "verify_btn", "inspect_btn")
        compat = (
            "diag_btn", "bridge_log_btn", "log_diagnostics_btn",
            "support_report_btn", "doom_logs_btn",
            "kharvox_folder_btn", "doom_prepare_btn", "doom_import_btn",
        )
        for name in install:
            self.assertIs(getattr(self.win, name).parent(), self.win.install_tools_panel)
        for name in compat:
            self.assertIs(getattr(self.win, name).parent(), self.win.more_tools_panel)
        self.assertIs(self.win.downloads.manual_review_button.parent(), self.win.downloads.review_actions)
        self.assertIs(self.win.downloads.inspect.parent(), self.win.downloads.review_actions)
        self.assertIs(self.win.downloads.download_button.parent(), self.win.downloads)
        for name in ("copy_btn", "inject_btn", "game_launch_btn",
                     "doom_probe_btn"):
            self.assertIs(getattr(self.win, name).parent(),
                          self.win.launch_tools_panel)
        self.assertIs(self.win.launch_tools_panel.parent(), self.win.overview_page)
        self.assertIs(self.win.check_btn.parent(), self.win.mod_updates)
        self.assertIs(self.win.mark_btn.parent(), self.win.update_tools_panel)


class ConsolidatedArchiveFolderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.page = GuidedDownloadsPage()
        self.page.show()
        self.app.processEvents()
        self.addCleanup(self.page.close)
        self.recipe = {"id": "cyberpunk-2077", "name": "Cyberpunk 2077"}
        self.page.set_recipe(self.recipe)

    def test_folder_actions_are_one_dropdown_plus_scan(self):
        self.assertEqual(self.page.action_toolbar.buttons,
                         (self.page.folder_menu_button, self.page.scan))
        self.assertEqual(self.page.folder_menu_button.text(), "Archive folder")
        self.assertEqual(len(self.page.folder_menu_actions), 4)
        for button in self.page.folder_menu_actions:
            self.assertFalse(button.isVisible())
            self.assertIs(button.parent(), self.page)

    def test_menu_actions_preserve_actual_folder_callbacks(self):
        button = self.page.set_game
        action = self.page.folder_menu_actions[button]
        self.page._sync_folder_actions()
        self.assertTrue(action.isEnabled())
        with mock.patch.object(self.page, "_choose_folder") as choose:
            action.trigger()
            choose.assert_called_once_with("game")

    def test_menu_respects_busy_state_and_never_bypasses_disabled_action(self):
        button = self.page.set_global
        action = self.page.folder_menu_actions[button]
        button.setEnabled(False)
        self.page._sync_folder_actions()
        self.assertFalse(action.isEnabled())
        with mock.patch.object(self.page, "_choose_folder") as choose:
            action.trigger()
            choose.assert_not_called()

    def test_scan_busy_state_disables_folder_menu_and_all_entries(self):
        busy = mock.MagicMock()
        busy.isRunning.return_value = True
        self.page.worker = busy
        self.page.set_recipe(self.recipe)
        self.assertFalse(self.page.folder_menu_button.isEnabled())
        self.page._sync_folder_actions()
        self.assertTrue(all(not action.isEnabled()
                            for action in self.page.folder_menu_actions.values()))
        self.page.worker = None

    def test_scan_button_remains_independent_of_folder_menu(self):
        self.assertTrue(self.page.scan.isEnabled())
        self.assertEqual(self.page.scan.text(), "Scan local archives")
        self.assertIn("No archives", self.page.scan.toolTip())


if __name__ == "__main__":
    unittest.main()
